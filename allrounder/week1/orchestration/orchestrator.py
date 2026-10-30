"""
orchestration/orchestrator.py - Intelligent Orchestrator & FSM with Human-in-the-Loop Gateway.

Design Patterns Used:
- Finite State Machine (FSM): Models execution states (RECEIVED -> GUARD_INPUT -> CACHE_CHECK -> INTENT_ROUTED -> RAG/TOOL/DIRECT -> HITL_PAUSED -> GUARD_OUTPUT -> COMPLETED).
- Command Pattern: PendingAction encapsulates paused requests awaiting human authorization.
"""

import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

try:
    from typesafe_sdk import Choice, Noul, TypeSafeClient
    TYPESAFE_AVAILABLE = True
except ImportError:
    TYPESAFE_AVAILABLE = False

try:
    from ..guardrails import output_guardrails
    from ..rag import rag_engine
    from ..tools import tool_registry
    from .state import ExecutionState, ExecutionStrategy, PendingAction, RiskLevel
except (ImportError, ValueError):
    from guardrails import output_guardrails
    from rag import rag_engine
    from tools import tool_registry
    from orchestration.state import ExecutionState, ExecutionStrategy, PendingAction, RiskLevel

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv()

logger = logging.getLogger("Orchestrator")

BASE_URL = (
    os.getenv("NGINX_PROXY_URL")
    or os.getenv("LITELLM_PROXY_URL")
    or os.getenv("AI_GATEWAY_URL")
    or "http://localhost:8080/v1"
)
API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")


class Orchestrator:
    """Intelligent FSM Execution Orchestrator with Human-in-the-Loop Gateway."""

    def __init__(self, base_url: str = BASE_URL, api_key: Optional[str] = API_KEY):
        self.base_url = base_url
        self.api_key = api_key or "sk-dummy"
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.pending_actions: Dict[str, PendingAction] = {}
        self.tool_registry = tool_registry
        self.output_guardrails = output_guardrails

        # System One Decision Model (Jev / TypeSafe AI)
        self.typesafe_api_key = os.getenv("TYPESAFE_API_KEY")
        self.jev_client: Optional[Any] = None
        if TYPESAFE_AVAILABLE and self.typesafe_api_key:
            try:
                self.jev_client = TypeSafeClient(api_key=self.typesafe_api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize TypeSafeClient for Jev in Orchestrator: {e}")

        # Domain keywords indicating documentation affinity
        self.rag_domain_keywords = [
            "setakeownershipprivilege",
            "privilege escalation",
            "privesc",
            "takeown",
            "icacls",
            "aws lab",
            "penetration testing lab",
            "cloudtrail",
            "vpc peering",
            "postgresql penetration",
            "pg_hba.conf",
            "postgres pentest",
            "wordlist",
            "rockyou",
            "seclists",
            "dirb",
            "wfuzz",
            "cewl",
            "crunch",
            "cupp",
            "kali linux wordlists",
            "hashcat postgres",
        ]

        # High-risk / offensive triggers necessitating Human-in-the-Loop review
        self.hitl_risk_triggers = [
            "exploit",
            "attack",
            "hack",
            "dump password",
            "steal",
            "bypass",
            "payload",
            "take ownership of system",
            "escalate to system",
            "brute force",
            "crack hash",
            "reverse shell",
            "destructive",
            "drop table",
            "exfiltrate",
            "weaponize",
            "privilege takeover",
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a registered tool or MCP adapter via ToolRegistry."""
        return self.tool_registry.execute(tool_name, arguments)

    def execute_with_tools(
        self, prompt: str, chosen_model: str = "cheap"
    ) -> Dict[str, Any]:
        """
        Executes an LLM call with function calling tools attached, dispatches any requested
        tool executions via ToolRegistry, and returns the final synthesized response along
        with tool telemetry.
        """
        tools_schema = self.tool_registry.get_openai_tools()
        if not tools_schema:
            r = self.client.chat.completions.create(
                model=chosen_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.2,
            )
            return {
                "answer": r.choices[0].message.content or "",
                "tool_calls": [],
                "tool_results": [],
                "model_used": r.model or chosen_model,
            }

        system_msg = {
            "role": "system",
            "content": (
                "You are an AI Security Gateway Assistant with access to registered tools "
                "(GitHub REST API, Prometheus MCP, Grafana MCP). When the user asks about repositories, "
                "metrics, latency, alerts, or dashboards, invoke the appropriate tool(s) and provide "
                "a clear, structured factual summary incorporating the returned tool data."
            ),
        }
        messages = [system_msg, {"role": "user", "content": prompt}]
        try:
            initial_resp = self.client.chat.completions.create(
                model=chosen_model,
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
                max_tokens=600,
                temperature=0.2,
            )
        except Exception as e:
            logger.warning(f"Initial tool completion failed: {e}. Retrying without tools.")
            initial_resp = self.client.chat.completions.create(
                model=chosen_model,
                messages=messages,
                max_tokens=600,
                temperature=0.2,
            )

        msg = initial_resp.choices[0].message
        tool_calls = msg.tool_calls or []
        executed_results = []

        if not tool_calls:
            return {
                "answer": msg.content or "",
                "tool_calls": [],
                "tool_results": [],
                "model_used": initial_resp.model or chosen_model,
            }

        messages.append(msg)
        for tc in tool_calls:
            t_name = tc.function.name
            try:
                t_args = json.loads(tc.function.arguments)
            except Exception:
                t_args = {}

            logger.info(f"Executing tool '{t_name}' with args {t_args}")
            try:
                tool_result = self.tool_registry.execute(t_name, t_args)
            except Exception as ex:
                tool_result = {"status": "error", "error": str(ex)}

            executed_results.append({
                "tool": t_name,
                "arguments": t_args,
                "result": tool_result,
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": t_name,
                "content": json.dumps(tool_result),
            })

        # Synthesize final answer incorporating tool execution results
        try:
            final_resp = self.client.chat.completions.create(
                model=chosen_model,
                messages=messages,
                max_tokens=800,
                temperature=0.2,
            )
            final_answer = final_resp.choices[0].message.content or ""
            model_returned = final_resp.model or chosen_model
        except Exception as e:
            logger.error(f"Synthesis following tool execution failed: {e}")
            final_answer = f"Executed {len(executed_results)} tool call(s):\n" + json.dumps(executed_results, indent=2)
            model_returned = chosen_model

        return {
            "answer": final_answer,
            "tool_calls": [
                {"name": tc.function.name, "arguments": tc.function.arguments}
                for tc in tool_calls
            ],
            "tool_results": executed_results,
            "model_used": model_returned,
        }

    def _infer_target_docs(self, prompt: str) -> List[str]:
        p_lower = prompt.lower()
        docs = []
        if any(w in p_lower for w in ["setakeownership", "takeown", "icacls", "windows", "privilege escalation", "privesc"]):
            docs.append("Windows Privilege Escalation: SeTakeOwnershipPrivilege")
        if any(w in p_lower for w in ["aws", "cloudtrail", "vpc", "peering", "penetration testing lab"]):
            docs.append("AWS: Penetration Testing Lab Setup")
        if any(w in p_lower for w in ["postgres", "postgresql", "pg_hba.conf", "hashcat postgres"]):
            docs.append("PostgreSQL Penetration Testing")
        if any(w in p_lower for w in ["wordlist", "rockyou", "seclists", "dirb", "wfuzz", "cewl", "crunch", "cupp"]):
            docs.append("Comprehensive Guide on Wordlists")
        return docs or ["Indexed Security Documentation"]

    def evaluate_with_jev(
        self, prompt: str
    ) -> Optional[Tuple[ExecutionStrategy, RiskLevel, str, List[str], List[str]]]:
        """
        Uses Jev System One decision model to rapidly classify intent, execution strategy,
        and calibrated risk probability without autoregressive token generation.
        """
        if not self.jev_client:
            return None

        try:
            resp = self.jev_client.system_one(
                state=f"User Query for Security Orchestration:\n{prompt}",
                questions={
                    "strategy": Choice(
                        criteria={
                            "DIRECT_LLM": "General queries, world facts, math, or coding questions unrelated to internal security documentation.",
                            "RAG_AUTOMATED": "Safe informational questions querying indexed documentation on Windows SeTakeOwnershipPrivilege, AWS labs, PostgreSQL pentesting, or Wordlists.",
                            "RAG_HUMAN_IN_THE_LOOP": "Offensive security actions, exploits, privilege escalation payloads, hash cracking, or system takeover requiring human security sign-off.",
                            "TOOL_CALL": "Requests to inspect GitHub repos, commits, files, or query Prometheus PromQL metrics, Grafana dashboards, or telemetry.",
                        }
                    ),
                    "risk_level": Choice(
                        criteria={
                            "LOW": "Benign informational or general query.",
                            "MEDIUM": "Defensive security concept or architectural inquiry.",
                            "HIGH": "Potentially offensive security request, exploit payload, or unauthorized system takeover.",
                            "CRITICAL": "Severe malicious exploit, weaponization, or destructive data loss action.",
                        }
                    ),
                    "is_offensive": Noul(),
                },
            )
            strat_val = resp.answers["strategy"].choice
            risk_val = resp.answers["risk_level"].choice
            is_offensive_prob = resp.answers["is_offensive"].noul
            strat_conf = getattr(resp.answers["strategy"], "confidence", 0.95)

            # Map to Enums
            strategy = ExecutionStrategy(strat_val)
            risk_level = RiskLevel(risk_val)

            target_docs = self._infer_target_docs(prompt)
            proposed_queries = rag_engine.generate_fused_queries(prompt, num_queries=3) if strategy in (ExecutionStrategy.RAG_AUTOMATED, ExecutionStrategy.RAG_HUMAN_IN_THE_LOOP) else []

            # If offensive probability exceeds high-risk threshold, enforce HITL
            if is_offensive_prob >= 0.70 and strategy != ExecutionStrategy.RAG_HUMAN_IN_THE_LOOP:
                strategy = ExecutionStrategy.RAG_HUMAN_IN_THE_LOOP
                risk_level = RiskLevel.HIGH
                reason = f"Jev System One high-risk offensive probability detected ({is_offensive_prob:.2f}). Mandatory human analyst sign-off."
            else:
                reason = f"Jev System One calibrated classification: {strat_val} (confidence: {strat_conf:.2f}, offensive P: {is_offensive_prob:.2f})"

            return strategy, risk_level, reason, proposed_queries, target_docs
        except Exception as e:
            logger.warning(f"Jev evaluation failed: {e}")
            return None

    def decide_strategy(
        self, prompt: str, chosen_model: str = "cheap", use_jev: bool = True
    ) -> Tuple[ExecutionStrategy, RiskLevel, str, List[str], List[str]]:
        """
        Evaluates prompt to determine:
        - Strategy: DIRECT_LLM, RAG_AUTOMATED, or RAG_HUMAN_IN_THE_LOOP
        - Risk Level: LOW, MEDIUM, HIGH, CRITICAL
        - Rationale: Explanation of decision
        - Proposed queries: RAG-Fusion search variations
        - Target docs: Candidate documents
        """
        # Fast Jev System One non-autoregressive decision if active
        if use_jev and self.jev_client:
            jev_decision = self.evaluate_with_jev(prompt)
            if jev_decision:
                return jev_decision
        p_lower = prompt.lower()
        matched_domain_terms = [k for k in self.rag_domain_keywords if k in p_lower]
        is_rag_candidate = len(matched_domain_terms) > 0

        matched_risk_terms = [t for t in self.hitl_risk_triggers if t in p_lower]
        is_high_risk = len(matched_risk_terms) > 0

        # Fast heuristic pass for tools (e.g. GitHub REST API, Prometheus / Grafana MCP)
        tool_keywords = [
            "github", "git repo", "repository issues", "github repo", "list commits", "search github",
            "prometheus", "promo", "grafana", "promql", "metrics", "p99 latency", "gateway latency",
            "token spend", "dashboard", "dashboards", "active alerts", "telemetry", "datasource"
        ]
        is_tool_candidate = any(w in p_lower for w in tool_keywords)
        if is_tool_candidate and not is_rag_candidate:
            return (
                ExecutionStrategy.TOOL_CALL,
                RiskLevel.LOW,
                "Tool or MCP invocation detected from user prompt (GitHub / Prometheus / Grafana).",
                [],
                [],
            )

        # Fast heuristic pass
        if not is_rag_candidate:
            generic_security_check = any(
                w in p_lower for w in ["database", "aws", "windows", "security", "permission", "password"]
            )
            if not generic_security_check:
                return (
                    ExecutionStrategy.DIRECT_LLM,
                    RiskLevel.LOW,
                    "General query not related to indexed security documentation. Direct LLM routing.",
                    [],
                    [],
                )

        # Advanced LLM Intent Classifier
        classification_prompt = (
            "You are an AI Security Gateway Orchestrator. Your role is to determine if an incoming user prompt:\n"
            "1. 'DIRECT_LLM': General question (e.g. general Python coding, world facts, chit-chat, math) where document search is not relevant.\n"
            "2. 'RAG_AUTOMATED': Safe, informational question about internal documentation (Windows SeTakeOwnershipPrivilege, AWS lab setup, PostgreSQL pentesting, Wordlists). Safe to retrieve and answer.\n"
            "3. 'RAG_HUMAN_IN_THE_LOOP': High-risk, offensive, destructive, or ambiguous security questions (e.g., executing privilege escalation exploits, cracking passwords, exfiltrating data, or taking over systems) where a human security analyst must review and approve the search queries before execution.\n"
            "4. 'TOOL_CALL': User requests inspecting GitHub repositories, reading code files, commits, issues, searching open-source projects, or querying Prometheus PromQL metrics, Grafana dashboards, system latency, or alerts.\n\n"
            f"User Prompt: \"{prompt}\"\n\n"
            "Respond in JSON format with fields:\n"
            "{\n"
            "  \"strategy\": \"DIRECT_LLM\" | \"RAG_AUTOMATED\" | \"RAG_HUMAN_IN_THE_LOOP\" | \"TOOL_CALL\",\n"
            "  \"risk_level\": \"LOW\" | \"MEDIUM\" | \"HIGH\" | \"CRITICAL\",\n"
            "  \"reason\": \"<Concise explanation>\",\n"
            "  \"target_docs\": [\"<Doc names like Windows PrivEsc, PostgreSQL Pentest, AWS Lab, Wordlists>\"],\n"
            "  \"proposed_queries\": [\"<Query 1>\", \"<Query 2>\", \"<Query 3>\"]\n"
            "}"
        )

        try:
            r = self.client.chat.completions.create(
                model="cheap",
                messages=[{"role": "user", "content": classification_prompt}],
                max_tokens=300,
                temperature=0.1,
            )
            raw = (r.choices[0].message.content or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)

            parsed = json.loads(raw)
            strategy = ExecutionStrategy(parsed.get("strategy", ExecutionStrategy.RAG_AUTOMATED.value))
            risk_level = RiskLevel(parsed.get("risk_level", RiskLevel.MEDIUM.value))
            reason = parsed.get("reason", "Orchestrator automated evaluation.")
            proposed_queries = parsed.get("proposed_queries", [])
            target_docs = parsed.get("target_docs", [])

            if is_high_risk and is_rag_candidate and strategy != ExecutionStrategy.RAG_HUMAN_IN_THE_LOOP:
                strategy = ExecutionStrategy.RAG_HUMAN_IN_THE_LOOP
                risk_level = RiskLevel.HIGH
                reason = f"Security Policy Trigger: Query requests offensive tactics ({', '.join(matched_risk_terms)}). Mandatory human analyst sign-off."

            return strategy, risk_level, reason, proposed_queries, target_docs

        except Exception as e:
            logger.warning(f"LLM classification failed ({e}), falling back to deterministic heuristic.")
            if is_rag_candidate:
                if is_high_risk:
                    return (
                        ExecutionStrategy.RAG_HUMAN_IN_THE_LOOP,
                        RiskLevel.HIGH,
                        f"Heuristic Risk Gate: Contains high-risk terms ({', '.join(matched_risk_terms)}). Requires human approval.",
                        rag_engine.generate_fused_queries(prompt, num_queries=3),
                        ["Indexed Security Documentation"],
                    )
                else:
                    return (
                        ExecutionStrategy.RAG_AUTOMATED,
                        RiskLevel.LOW,
                        "Informational query matching documentation keywords. Running automated RAG.",
                        rag_engine.generate_fused_queries(prompt, num_queries=3),
                        ["Indexed Security Documentation"],
                    )
            else:
                return (
                    ExecutionStrategy.DIRECT_LLM,
                    RiskLevel.LOW,
                    "General query outside documentation scope. Routing directly to LLM.",
                    [],
                    [],
                )

    def create_pending_action(
        self,
        user_prompt: str,
        model: str,
        strategy: ExecutionStrategy,
        risk_level: RiskLevel,
        reason: str,
        proposed_queries: List[str],
        target_docs: List[str],
    ) -> PendingAction:
        """Creates and stores a pending action requiring human authorization."""
        action_id = str(uuid.uuid4())[:8]
        if not proposed_queries:
            proposed_queries = rag_engine.generate_fused_queries(user_prompt, num_queries=3)

        action = PendingAction(
            action_id=action_id,
            user_prompt=user_prompt,
            model=model,
            strategy=strategy,
            risk_level=risk_level,
            reason=reason,
            proposed_queries=proposed_queries,
            target_docs=target_docs,
        )
        self.pending_actions[action_id] = action
        logger.info(f"Created HITL Pending Action [{action_id}]: {reason}")
        return action

    def get_pending_action(self, action_id: str) -> Optional[PendingAction]:
        return self.pending_actions.get(action_id)

    def list_pending_actions(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self.pending_actions.values() if a.status == "pending"]

    def resolve_action(
        self,
        action_id: str,
        decision: str,  # "approve", "modify", "reject"
        modified_query: Optional[str] = None,
        modified_queries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Executes human operator's decision: approve, modify, or reject."""
        action = self.pending_actions.get(action_id)
        if not action:
            return {"success": False, "error": f"Action ID '{action_id}' not found."}

        action.decision = decision
        action.status = decision

        if decision == "approve":
            logger.info(f"Human approved action [{action_id}]. Executing RAG retrieval...")
            rag_res = rag_engine.query(
                prompt=action.user_prompt,
                model=action.model,
                fused_queries=action.proposed_queries,
            )
            ctx_texts = [c.get("content", "") for c in rag_res.get("top_chunks", []) if isinstance(c, dict)]
            out_guard = self.output_guardrails.inspect(
                output_text=rag_res["answer"],
                retrieved_context=ctx_texts,
            )
            rag_res["answer"] = out_guard.sanitized_output
            action.result = rag_res
            return {
                "success": True,
                "status": "approved",
                "action_id": action_id,
                "response": out_guard.sanitized_output,
                "citations": rag_res["citations"],
                "fused_queries": rag_res["fused_queries"],
                "top_chunks": rag_res["top_chunks"],
                "dedup_count": rag_res["dedup_count"],
                "latency_ms": rag_res["latency_ms"],
                "model_used": rag_res["model_used"],
                "output_guardrails": out_guard.to_dict(),
            }

        elif decision == "modify":
            active_prompt = modified_query or action.user_prompt
            active_queries = modified_queries or [active_prompt]
            action.modified_query = active_prompt
            logger.info(f"Human modified action [{action_id}] query to: '{active_prompt}'")
            rag_res = rag_engine.query(
                prompt=active_prompt,
                model=action.model,
                fused_queries=active_queries,
            )
            ctx_texts = [c.get("content", "") for c in rag_res.get("top_chunks", []) if isinstance(c, dict)]
            out_guard = self.output_guardrails.inspect(
                output_text=rag_res["answer"],
                retrieved_context=ctx_texts,
            )
            rag_res["answer"] = out_guard.sanitized_output
            action.result = rag_res
            return {
                "success": True,
                "status": "modified_and_executed",
                "action_id": action_id,
                "response": out_guard.sanitized_output,
                "citations": rag_res["citations"],
                "fused_queries": rag_res["fused_queries"],
                "top_chunks": rag_res["top_chunks"],
                "dedup_count": rag_res["dedup_count"],
                "latency_ms": rag_res["latency_ms"],
                "model_used": rag_res["model_used"],
                "output_guardrails": out_guard.to_dict(),
            }

        elif decision == "reject":
            logger.info(f"Human rejected action [{action_id}]. Bypassing RAG...")
            refusal_instruction = (
                "The human security operator rejected automated document retrieval/exploit access for this request.\n"
                "Provide a high-level educational/defensive overview only, without giving actionable exploit steps."
            )
            resp = self.client.chat.completions.create(
                model=action.model,
                messages=[
                    {"role": "system", "content": refusal_instruction},
                    {"role": "user", "content": action.user_prompt},
                ],
                max_tokens=400,
                temperature=0.2,
            )
            answer = resp.choices[0].message.content or "Action cancelled by human administrator."
            out_guard = self.output_guardrails.inspect(output_text=answer)
            return {
                "success": True,
                "status": "rejected",
                "action_id": action_id,
                "response": out_guard.sanitized_output,
                "citations": [],
                "fused_queries": [],
                "top_chunks": [],
                "dedup_count": 0,
                "latency_ms": 0,
                "model_used": resp.model or action.model,
                "output_guardrails": out_guard.to_dict(),
            }

        return {"success": False, "error": f"Invalid decision: {decision}"}


# Default singleton instance
orchestrator = Orchestrator()
