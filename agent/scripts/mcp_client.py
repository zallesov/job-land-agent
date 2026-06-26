"""Python MCP client for JobLand records.

All JobLand job/interview data MUST flow through the JobLand MCP server, never
through a direct PocketBase/backend client. This is a thin JSON-RPC-over-HTTP
client that speaks the MCP Streamable HTTP protocol to mcp.zall.dev.

Config from .env:
  MCP_JOBLAND_URL       (default https://mcp.zall.dev/mcp)
  MCP_JOBLAND_API_KEY   (required — Bearer token)

Only jobs_* tools are wrapped here; that is all the ingest -> enrichment
pipeline needs. Other collections (assessments/research/companies/pipeline_runs)
are not yet exposed by the MCP server.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_DEFAULT_URL = "https://mcp.zall.dev/mcp"


def _load_env() -> None:
    root = Path(__file__).parent.parent
    for candidate in [
        root / ".env",
        Path(os.environ.get("HERMES_PROFILE_DIR", "")) / ".env",
    ]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
            break


_load_env()


def _make_ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


class MCPError(RuntimeError):
    """Raised when the MCP server returns a JSON-RPC or tool error."""


class MCPClient:
    """Thin MCP Streamable-HTTP JSON-RPC client (jobs_* tools)."""

    def __init__(self) -> None:
        self._url = os.environ.get("MCP_JOBLAND_URL", _DEFAULT_URL)
        self._token = os.environ.get("MCP_JOBLAND_API_KEY", "")
        self._ssl_context = _make_ssl_context()
        self._id = 0

    # --- transport ---

    def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Invoke an MCP tool, returning the parsed JSON payload."""
        if not self._token:
            raise MCPError("MCP_JOBLAND_API_KEY is not set")
        self._id += 1
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": self._id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }).encode()
        req = urllib.request.Request(
            self._url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {self._token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60, context=self._ssl_context) as r:
                raw = r.read().decode(errors="replace")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")[:400]
            raise MCPError(f"MCP {tool}: HTTP {e.code} — {err_body}") from e
        return self._parse(tool, raw)

    @staticmethod
    def _parse(tool: str, raw: str) -> Any:
        # The Streamable HTTP transport replies as an SSE stream; the JSON-RPC
        # envelope is on the last `data:` line. A plain JSON body is also valid.
        payload_line = raw.strip()
        data_lines = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
        if data_lines:
            payload_line = data_lines[-1]
        try:
            envelope = json.loads(payload_line)
        except json.JSONDecodeError as e:
            raise MCPError(f"MCP {tool}: unparseable response: {raw[:300]}") from e

        if "error" in envelope:
            raise MCPError(f"MCP {tool}: {envelope['error']}")
        result = envelope.get("result", {})
        if result.get("isError"):
            raise MCPError(f"MCP {tool}: {_first_text(result)}")
        # Prefer the structured payload; fall back to the text content (a JSON
        # string of the record or array).
        if "structuredContent" in result and "result" in result["structuredContent"]:
            return result["structuredContent"]["result"]
        text = _first_text(result)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    # --- jobs tools (high-level, mirrors the old pb_client surface) ---

    def get_job(self, job_id: Any) -> dict | None:
        try:
            rec = self._call("jobs_get", {"id": str(job_id)})
        except MCPError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return None
            raise
        return rec or None

    def insert_job(self, **fields: Any) -> str:
        rec = self._call("jobs_create", {"fields": fields})
        return rec["id"]

    def update_job(self, job_id: Any, **fields: Any) -> None:
        self._call("jobs_update", {"id": str(job_id), "fields": fields})

    def update_job_status(self, job_id: Any, status: str, comment: str | None = None) -> None:
        fields: dict[str, Any] = {"status": status}
        if comment is not None:
            fields["comment"] = comment
        self._call("jobs_update", {"id": str(job_id), "fields": fields})

    def find_job_by_url(self, url: str) -> dict | None:
        return self._call("jobs_find_by_url", {"url": url}) or None

    def list_jobs(self, filter_str: str = "", per_page: int = 200) -> list[dict]:
        """Single page of jobs (newest first)."""
        args: dict[str, Any] = {"perPage": per_page}
        if filter_str:
            args["filter"] = filter_str
        result = self._call("jobs_list", args)
        return result if isinstance(result, list) else result.get("items", [])

    def list_all_jobs(self, filter_str: str = "", per_page: int = 200) -> list[dict]:
        """Page through every matching job (used to seed local dedup)."""
        out: list[dict] = []
        page = 1
        while True:
            args: dict[str, Any] = {"page": page, "perPage": per_page}
            if filter_str:
                args["filter"] = filter_str
            batch = self._call("jobs_list", args)
            items = batch if isinstance(batch, list) else batch.get("items", [])
            out.extend(items)
            if len(items) < per_page:
                break
            page += 1
        return out


def _first_text(result: dict) -> str | None:
    for block in result.get("content", []) or []:
        if block.get("type") == "text":
            return block.get("text")
    return None


_client: MCPClient | None = None


def get_client() -> MCPClient:
    """Process-wide MCP client singleton."""
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
