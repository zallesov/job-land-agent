"""In-memory MCP client double for tests.

Mirrors the high-level surface of scripts.mcp_client.MCPClient (get_job,
insert_job, update_job, update_job_status, find_job_by_url, list_jobs,
list_all_jobs) against an in-memory store, plus low-level create/get helpers so
tests can seed and assert directly. Never touches the network or any MCP server.
"""
from __future__ import annotations

from typing import Any


class FakeMCPClient:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self._counter = 0

    # --- low-level helpers for tests ---

    def _next_id(self) -> str:
        self._counter += 1
        return f"fake{self._counter:011d}"

    def create(self, collection: str, data: dict) -> dict:
        assert collection == "jobs", "fake MCP only handles jobs"
        rid = data.get("id") or self._next_id()
        rec = {"id": rid, **data}
        self.jobs[rid] = rec
        return rec

    def get(self, collection: str, record_id: str) -> dict | None:
        assert collection == "jobs", "fake MCP only handles jobs"
        return self.jobs.get(record_id)

    # --- high-level MCPClient surface ---

    def get_job(self, job_id: Any) -> dict | None:
        return self.jobs.get(str(job_id))

    def insert_job(self, **fields: Any) -> str:
        return self.create("jobs", fields)["id"]

    def update_job(self, job_id: Any, **fields: Any) -> None:
        rec = self.jobs.setdefault(str(job_id), {"id": str(job_id)})
        rec.update(fields)

    def update_job_status(self, job_id: Any, status: str, comment: str | None = None) -> None:
        fields: dict[str, Any] = {"status": status}
        if comment is not None:
            fields["comment"] = comment
        self.update_job(job_id, **fields)

    def find_job_by_url(self, url: str) -> dict | None:
        for rec in self.jobs.values():
            if rec.get("url") == url:
                return rec
        return None

    def _match(self, filter_str: str) -> list[dict]:
        """Minimal filter support: `field = "value"` clauses joined by &&.

        Enough for the pipeline's queries (provider/status). Always excludes
        soft-deleted rows, mirroring the MCP server's implicit deleted_at = null.
        """
        import re

        clauses = re.findall(r'(\w+)\s*=\s*"([^"]*)"', filter_str or "")
        out = []
        for rec in self.jobs.values():
            if rec.get("deleted_at"):
                continue
            if all(str(rec.get(field, "")) == value for field, value in clauses):
                out.append(rec)
        return out

    def list_jobs(self, filter_str: str = "", per_page: int = 200) -> list[dict]:
        return self._match(filter_str)[:per_page]

    def list_all_jobs(self, filter_str: str = "", per_page: int = 200) -> list[dict]:
        return self._match(filter_str)
