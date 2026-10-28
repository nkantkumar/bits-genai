"""
Orchestrator.py - Intelligent Execution Orchestrator with Human-in-the-Loop (HITL) Gateways.

Sits immediately after the Smart Router in the AI Gateway pipeline.
Determines whether an incoming prompt:
1. DIRECT_LLM:
   - Query is general knowledge, math, coding unrelated to docs, or conversational.
   - No RAG needed; routes directly to upstream LLM.
2. RAG_AUTOMATED:
   - Safe informational query matching docs/ knowledge base (Windows PrivEsc, AWS Lab, Postgres Pentesting, Wordlists).
   - Executes RAG-Fusion, PGVector retrieval, RRF ranking, deduplication, and grounded synthesis automatically.
3. RAG_HUMAN_IN_THE_LOOP (HITL):
   - High-risk security queries, actionable exploit instructions, credential attacks, or high-stakes operations.
   - Halts automated execution; generates a Pending HITL Action with proposed search queries and risk rationale.
   - Awaits human authorization (Approve, Modify Query, or Reject).
"""

import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

# Ensure week1 is on sys.path
WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from RagEngine import rag_engine
from ToolRegistry import tool_registry
from OutputGuardrails import output_guardrails

# Load environment
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

logger = logging.getLogger("Orchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

BASE_URL = (
    os.getenv("NGINX_PROXY_URL")
    or os.getenv("LITELLM_PROXY_URL")
    or os.getenv("AI_GATEWAY_URL")
    or "http://localhost:8080/v1"
)
API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")


class ExecutionStrategy(str, Enum):
    DIRECT_LLM = "DIRECT_LLM"
    RAG_AUTOMATED = "RAG_AUTOMATED"
    RAG_HUMAN_IN_THE_LOOP = "RAG_HUMAN_IN_THE_LOOP"
    TOOL_CALL = "TOOL_CALL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class PendingAction:
    action_id: str
    user_prompt: str
    model: str
    strategy: ExecutionStrategy
    risk_level: RiskLevel
    reason: str
    proposed_queries: List[str]
    target_docs: List[str]
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, approved, modified, rejected
    decision: Optional[str] = None
    modified_query: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value
        d["risk_level"] = self.risk_level.value
        return d


class Orchestrator:
    def __init__(self, base_url: str = BASE_URL, api_key: Optional[str] = API_KEY):
        self.base_url = base_url
        self.api_key = api_key or "sk-dummy"
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.pending_actions: Dict[str, PendingAction] = {}
        self.tool_registry = tool_registry
        self.output_guardrails = output_guardrails

        # Keywords that indicate internal documentation domain
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

        # High-risk / offensive triggers that necessitate Human-in-the-Loop approval
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

    # -------------------------------------------------------------------------
    # 1. Intent & Risk Classification
    # -------------------------------------------------------------------------
    def decide_strategy(self, prompt: str, chosen_model: str = "cheap") -> Tuple[ExecutionStrategy, RiskLevel, str, List[str], List[str]]:
        """
        Evaluates the prompt to decide:
        - Strategy: DIRECT_LLM, RAG_AUTOMATED, or RAG_HUMAN_IN_THE_LOOP
        - Risk Level: LOW, MEDIUM, HIGH, CRITICAL
        - Rationale: Explanation of the decision
        - Proposed queries: RAG-Fusion search queries
        - Target docs: Candidate documents
        """
        p_lower = prompt.lower()

        # Step A: Check domain affinity with docs/ folder
        matched_domain_terms = [k for k in self.rag_domain_keywords if k in p_lower]
        is_rag_candidate = len(matched_domain_terms) > 0

        # Step B: Check high-risk offensive/destructive keywords
        matched_risk_terms = [t for t in self.hitl_risk_triggers if t in p_lower]
        is_high_risk = len(matched_risk_terms) > 0

        # Fast heuristic pass
        if not is_rag_candidate:
            # Check if query mentions security tools/concepts broadly
            generic_security_check = any(w in p_lower for w in ["database", "aws", "windows", "security", "permission", "password"])
            if not generic_security_check:
                return (
                    ExecutionStrategy.DIRECT_LLM,
                    RiskLevel.LOW,
                    "General query not related to indexed security documentation. Direct LLM routing.",
                    [],
                    [],
                )

        # Advanced LLM Intent Classifier for nuanced decisions
        classification_prompt = (
            "You are an AI Security Gateway Orchestrator. Your role is to determine if an incoming user prompt:\n"
            "1. 'DIRECT_LLM': General question (e.g. general Python coding, world facts, chit-chat, math) where document search is not relevant.\n"
            "2. 'RAG_AUTOMATED': Safe, informational question about internal documentation (Windows SeTakeOwnershipPrivilege, AWS lab setup, PostgreSQL pentesting, Wordlists). Safe to retrieve and answer.\n"
            "3. 'RAG_HUMAN_IN_THE_LOOP': High-risk, offensive, destructive, or ambiguous security questions (e.g., executing privilege escalation exploits, cracking passwords, exfiltrating data, or taking over systems) where a human security analyst must review and approve the search queries before execution.\n\n"
            f"User Prompt: \"{prompt}\"\n\n"
            "Respond in JSON format with fields:\n"
            "{\n"
            "  \"strategy\": \"DIRECT_LLM\" | \"RAG_AUTOMATED\" | \"RAG_HUMAN_IN_THE_LOOP\",\n"
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
            # Strip markdown code blocks if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)

            parsed = json.loads(raw)
            strategy = ExecutionStrategy(parsed.get("strategy", ExecutionStrategy.RAG_AUTOMATED.value))
            risk_level = RiskLevel(parsed.get("risk_level", RiskLevel.MEDIUM.value))
            reason = parsed.get("reason", "Orchestrator automated evaluation.")
            proposed_queries = parsed.get("proposed_queries", [])
            target_docs = parsed.get("target_docs", [])

            # Safety fallback: If high-risk terms matched heuristically, enforce HITL
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

    # -------------------------------------------------------------------------
    # 2. Human-in-the-Loop (HITL) Lifecycle Management
    # -------------------------------------------------------------------------
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
        """Creates and stores a pending action requiring human approval."""
        action_id = str(uuid.uuid4())[:8]

        # Ensure we have proposed queries ready for the user to review/edit
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
        """Retrieve a pending action by its ID."""
        return self.pending_actions.get(action_id)

    def list_pending_actions(self) -> List[Dict[str, Any]]:
        """List all currently pending actions."""
        return [
            a.to_dict()
            for a in self.pending_actions.values()
            if a.status == "pending"
        ]

    def resolve_action(
        self,
        action_id: str,
        decision: str,  # "approve", "modify", "reject"
        modified_query: Optional[str] = None,
        modified_queries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the human operator's decision:
        - "approve": Runs RAG with the proposed queries.
        - "modify": Runs RAG with the human-adjusted query/queries.
        - "reject": Skips RAG retrieval; executes safe direct LLM answer or policy notice.
        """
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
            # Use modified queries provided by the human
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
            # Route to direct LLM with strict defensive instructions
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


# Singleton Orchestrator instance
orchestrator = Orchestrator()


if __name__ == "__main__":
    print("=" * 70)
    print(" Testing Orchestrator Decisions & Human-in-the-Loop Gateway")
    print("=" * 70)

    test_queries = [
        # 1. Pure General LLM (No RAG needed)
        "What is the capital of Australia and what is its population?",
        # 2. Automated RAG (Informational documentation query)
        "Can you explain the purpose of SeTakeOwnershipPrivilege in Windows?",
        # 3. High-Risk Human-in-the-Loop (Exploit execution / attack commands)
        "Provide step-by-step commands to exploit SeTakeOwnershipPrivilege and take over system files on a target machine.",
    ]

    for q in test_queries:
        strat, risk, reason, queries, docs = orchestrator.decide_strategy(q, chosen_model="smart")
        print(f"\nQuery: \"{q}\"")
        print(f" -> Strategy:   {strat.value}")
        print(f" -> Risk Level: {risk.value}")
        print(f" -> Reason:     {reason}")
        if queries:
            print(f" -> Proposed:   {queries[:2]}")
        if strat == ExecutionStrategy.RAG_HUMAN_IN_THE_LOOP:
            action = orchestrator.create_pending_action(
                user_prompt=q,
                model="smart",
                strategy=strat,
                risk_level=risk,
                reason=reason,
                proposed_queries=queries,
                target_docs=docs,
            )
            print(f" -> [HITL PENDING ACTION CREATED]: ID={action.action_id}")
            # Simulate approval
            res = orchestrator.resolve_action(action.action_id, decision="approve")
            print(f" -> [HITL APPROVED ANSWER PREVIEW]: {res['response'][:160]}...")
