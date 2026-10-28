"""
tools/github_tool.py - GitHub REST API Tool Adapter (Adapter Pattern).

Design Pattern:
- Adapter Pattern: Bridges external GitHub REST API v3 into the uniform BaseTool interface.
  Enables AI agents and orchestrators to inspect repositories, read code files, list issues,
  search open-source projects, and fetch commit history with zero orchestrator coupling.
"""

import base64
import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    try:
        SSL_CONTEXT = ssl.create_default_context()
    except Exception:
        SSL_CONTEXT = ssl._create_unverified_context()

from .base import BaseTool, ToolDefinition, ToolParameterSchema

logger = logging.getLogger("GitHubToolAdapter")


class GitHubToolAdapter(BaseTool):
    """
    Adapter Pattern implementation for GitHub REST API v3.
    Supports authenticated or public unauthenticated queries with automatic rate-limit tracking,
    base64 file decoding, and graceful offline fallback.
    """

    DEFAULT_BASE_URL = "https://api.github.com"

    def __init__(
        self,
        api_token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 8.0,
    ):
        self.api_token = (
            api_token
            or os.getenv("GITHUB_TOKEN")
            or os.getenv("GITHUB_API_TOKEN")
            or os.getenv("GH_TOKEN")
        )
        self.base_url = (base_url or os.getenv("GITHUB_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="github_api",
            description=(
                "Interact with GitHub REST API to inspect repositories, read code files, "
                "search open-source projects, view issues, and fetch commit history."
            ),
            parameters=ToolParameterSchema(
                properties={
                    "action": {
                        "type": "string",
                        "enum": [
                            "get_repo",
                            "get_file_content",
                            "list_issues",
                            "search_repositories",
                            "get_user",
                            "list_commits",
                        ],
                        "description": "The GitHub operation to perform.",
                    },
                    "owner": {
                        "type": "string",
                        "description": "Repository owner or organization name (e.g. 'openai', 'octocat').",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name (e.g. 'Hello-World', 'bits-genai').",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path within repository for 'get_file_content' (e.g. 'README.md', 'src/main.py').",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search term for 'search_repositories' (e.g. 'ai gateway python').",
                    },
                    "username": {
                        "type": "string",
                        "description": "GitHub username for 'get_user' (e.g. 'torvalds', 'octocat').",
                    },
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Issue state filter for 'list_issues' (default: 'open').",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10, max: 30).",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Git branch, tag, or commit SHA for 'get_file_content'.",
                    },
                },
                required=["action"],
            ),
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "AI-Gateway-GitHubTool/1.0",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _make_request(
        self, endpoint: str, query_params: Optional[Dict[str, Any]] = None, method: str = "GET"
    ) -> Dict[str, Any]:
        """Performs HTTPS request to GitHub REST API with rate-limit capture."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if query_params:
            filtered = {k: v for k, v in query_params.items() if v is not None}
            if filtered:
                qs = urllib.parse.urlencode(filtered)
                url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"

        req = urllib.request.Request(url, headers=self._get_headers(), method=method)

        try:
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=self.timeout) as resp:
                status_code = resp.status
                rate_remaining = resp.headers.get("x-ratelimit-remaining")
                rate_limit = resp.headers.get("x-ratelimit-limit")
                raw_body = resp.read().decode("utf-8")
                data = json.loads(raw_body) if raw_body else {}

                return {
                    "status": "success",
                    "http_status": status_code,
                    "authenticated": bool(self.api_token),
                    "rate_limit_remaining": rate_remaining,
                    "rate_limit_total": rate_limit,
                    "data": data,
                }
        except urllib.error.HTTPError as e:
            raw_err = e.read().decode("utf-8") if hasattr(e, "read") else ""
            err_json = {}
            try:
                err_json = json.loads(raw_err)
            except Exception:
                pass

            error_msg = err_json.get("message", str(e))
            logger.warning(f"GitHub API HTTP error {e.code}: {error_msg} for URL {url}")

            if e.code == 401:
                guidance = "Authentication failed. Please verify your GITHUB_TOKEN."
            elif e.code == 403 and "rate limit" in error_msg.lower():
                guidance = "GitHub API rate limit exceeded. Provide a personal access token via GITHUB_TOKEN."
            elif e.code == 404:
                guidance = "Requested GitHub resource was not found. Check repository or file path spelling."
            else:
                guidance = f"GitHub API responded with HTTP {e.code}."

            return {
                "status": "error",
                "http_status": e.code,
                "error": error_msg,
                "guidance": guidance,
                "url": url,
            }
        except Exception as e:
            logger.error(f"GitHub API connection failure: {e}")
            # Graceful mock response for offline / isolated development
            return {
                "status": "error",
                "simulated_mock": True,
                "error": str(e),
                "guidance": "Connection failed. Returned simulated fallback for offline resilience.",
                "url": url,
            }

    def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetches metadata for a repository."""
        res = self._make_request(f"repos/{owner}/{repo}")
        if res.get("status") == "success" and isinstance(res.get("data"), dict):
            d = res["data"]
            res["summary"] = {
                "full_name": d.get("full_name"),
                "description": d.get("description"),
                "stars": d.get("stargazers_count"),
                "forks": d.get("forks_count"),
                "open_issues": d.get("open_issues_count"),
                "language": d.get("language"),
                "default_branch": d.get("default_branch"),
                "html_url": d.get("html_url"),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
            }
        return res

    def get_file_content(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches and decodes file content from a repository."""
        clean_path = path.lstrip("/")
        params = {"ref": ref} if ref else None
        res = self._make_request(f"repos/{owner}/{repo}/contents/{clean_path}", query_params=params)

        if res.get("status") == "success" and isinstance(res.get("data"), dict):
            data = res["data"]
            encoding = data.get("encoding")
            raw_content = data.get("content", "")

            if encoding == "base64" and raw_content:
                try:
                    decoded = base64.b64decode(raw_content).decode("utf-8", errors="replace")
                except Exception as ex:
                    decoded = f"[Binary or undecodable content: {ex}]"
            else:
                decoded = raw_content

            # Truncate overly long files to avoid token overflow in LLM context
            is_truncated = len(decoded) > 8000
            display_content = decoded[:8000] + "\n...[TRUNCATED FILE CONTENT]" if is_truncated else decoded

            res["file"] = {
                "name": data.get("name"),
                "path": data.get("path"),
                "size_bytes": data.get("size"),
                "sha": data.get("sha"),
                "content": display_content,
                "is_truncated": is_truncated,
                "html_url": data.get("html_url"),
            }
        return res

    def list_issues(
        self, owner: str, repo: str, state: str = "open", per_page: int = 10
    ) -> Dict[str, Any]:
        """Lists issues for a repository."""
        params = {"state": state, "per_page": min(per_page, 30)}
        res = self._make_request(f"repos/{owner}/{repo}/issues", query_params=params)

        if res.get("status") == "success" and isinstance(res.get("data"), list):
            issues_summary = []
            for item in res["data"]:
                # GitHub issues endpoint includes pull requests unless filtered
                is_pr = "pull_request" in item
                issues_summary.append({
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "is_pull_request": is_pr,
                    "user": item.get("user", {}).get("login"),
                    "comments": item.get("comments"),
                    "created_at": item.get("created_at"),
                    "html_url": item.get("html_url"),
                })
            res["issues"] = issues_summary
            res["count"] = len(issues_summary)
        return res

    def search_repositories(
        self, query: str, sort: str = "stars", per_page: int = 5
    ) -> Dict[str, Any]:
        """Searches GitHub repositories by keyword."""
        params = {"q": query, "sort": sort, "per_page": min(per_page, 30)}
        res = self._make_request("search/repositories", query_params=params)

        if res.get("status") == "success" and isinstance(res.get("data"), dict):
            items = res["data"].get("items", [])
            repos_summary = []
            for r in items:
                repos_summary.append({
                    "full_name": r.get("full_name"),
                    "description": r.get("description"),
                    "stars": r.get("stargazers_count"),
                    "forks": r.get("forks_count"),
                    "language": r.get("language"),
                    "html_url": r.get("html_url"),
                })
            res["repositories"] = repos_summary
            res["total_count"] = res["data"].get("total_count", 0)
        return res

    def get_user(self, username: str) -> Dict[str, Any]:
        """Fetches public user or organization profile."""
        res = self._make_request(f"users/{username}")
        if res.get("status") == "success" and isinstance(res.get("data"), dict):
            u = res["data"]
            res["user"] = {
                "login": u.get("login"),
                "name": u.get("name"),
                "company": u.get("company"),
                "bio": u.get("bio"),
                "public_repos": u.get("public_repos"),
                "followers": u.get("followers"),
                "following": u.get("following"),
                "html_url": u.get("html_url"),
            }
        return res

    def list_commits(self, owner: str, repo: str, per_page: int = 5) -> Dict[str, Any]:
        """Lists recent commits for a repository."""
        params = {"per_page": min(per_page, 30)}
        res = self._make_request(f"repos/{owner}/{repo}/commits", query_params=params)

        if res.get("status") == "success" and isinstance(res.get("data"), list):
            commits = []
            for c in res["data"]:
                commit_info = c.get("commit", {})
                author_info = commit_info.get("author", {})
                commits.append({
                    "sha": c.get("sha", "")[:7],
                    "message": commit_info.get("message", "").split("\n")[0],
                    "author": author_info.get("name"),
                    "date": author_info.get("date"),
                    "html_url": c.get("html_url"),
                })
            res["commits"] = commits
            res["count"] = len(commits)
        return res

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Dispatches execution to the appropriate GitHub REST API endpoint.
        Handles flexible parameter passing (e.g. repo='owner/repo' or separate owner/repo).
        """
        action = params.get("action")
        if not action:
            return {
                "status": "error",
                "error": "Missing required parameter 'action'.",
                "valid_actions": [
                    "get_repo",
                    "get_file_content",
                    "list_issues",
                    "search_repositories",
                    "get_user",
                    "list_commits",
                ],
            }

        # Helper to split "owner/repo" shorthand if passed in repo or owner
        owner = params.get("owner", "")
        repo = params.get("repo", "")
        if "/" in repo and not owner:
            owner, repo = repo.split("/", 1)
        elif "/" in owner and not repo:
            owner, repo = owner.split("/", 1)

        if action == "get_repo":
            if not owner or not repo:
                return {"status": "error", "error": "Both 'owner' and 'repo' are required for 'get_repo'."}
            return self.get_repo(owner=owner, repo=repo)

        elif action == "get_file_content":
            path = params.get("path")
            if not owner or not repo or not path:
                return {
                    "status": "error",
                    "error": "'owner', 'repo', and 'path' are required for 'get_file_content'.",
                }
            return self.get_file_content(owner=owner, repo=repo, path=path, ref=params.get("ref"))

        elif action == "list_issues":
            if not owner or not repo:
                return {"status": "error", "error": "Both 'owner' and 'repo' are required for 'list_issues'."}
            state = params.get("state", "open")
            per_page = int(params.get("per_page", 10))
            return self.list_issues(owner=owner, repo=repo, state=state, per_page=per_page)

        elif action == "search_repositories":
            query = params.get("query")
            if not query:
                return {"status": "error", "error": "'query' is required for 'search_repositories'."}
            per_page = int(params.get("per_page", 5))
            return self.search_repositories(query=query, per_page=per_page)

        elif action == "get_user":
            username = params.get("username")
            if not username:
                return {"status": "error", "error": "'username' is required for 'get_user'."}
            return self.get_user(username=username)

        elif action == "list_commits":
            if not owner or not repo:
                return {"status": "error", "error": "Both 'owner' and 'repo' are required for 'list_commits'."}
            per_page = int(params.get("per_page", 5))
            return self.list_commits(owner=owner, repo=repo, per_page=per_page)

        else:
            return {
                "status": "error",
                "error": f"Unknown action '{action}'.",
                "valid_actions": [
                    "get_repo",
                    "get_file_content",
                    "list_issues",
                    "search_repositories",
                    "get_user",
                    "list_commits",
                ],
            }


# Alias for convenience
GitHubApiTool = GitHubToolAdapter
