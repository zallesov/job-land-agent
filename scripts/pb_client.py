"""PocketBase REST client for Python scripts.

Config from .env: POCKETBASE_URL, POCKETBASE_ADMIN_EMAIL, POCKETBASE_ADMIN_PASSWORD
No external dependencies — stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def pad_id(id_val: Any) -> str:
    """Convert numeric ID to 15-char zero-padded PocketBase ID string."""
    try:
        return str(int(id_val)).zfill(15)
    except (ValueError, TypeError):
        return str(id_val)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PBClient:
    """Thin PocketBase REST client. Authenticates as admin superuser."""

    def __init__(self) -> None:
        self._base = os.environ.get("POCKETBASE_URL", "http://localhost:8090").rstrip("/")
        self._email = os.environ.get("POCKETBASE_ADMIN_EMAIL", "")
        self._password = os.environ.get("POCKETBASE_ADMIN_PASSWORD", "")
        self._token: str | None = None
        self._token_exp: float = 0
        self._ssl_context = self._make_ssl_context()

    @staticmethod
    def _make_ssl_context() -> ssl.SSLContext | None:
        try:
            import certifi  # type: ignore
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return None

    def _ensure_auth(self) -> str:
        if self._token and time.time() < self._token_exp:
            return self._token
        data = json.dumps({"identity": self._email, "password": self._password}).encode()
        req = urllib.request.Request(
            f"{self._base}/api/collections/_superusers/auth-with-password",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15, context=self._ssl_context) as r:
            body = json.loads(r.read())
        self._token = body["token"]
        self._token_exp = time.time() + 55 * 60
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": self._ensure_auth(),
        }

    def _req(self, method: str, path: str, body: dict | None = None) -> Any:
        url = f"{self._base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=30, context=self._ssl_context) as r:
                text = r.read()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")[:400]
            raise RuntimeError(f"PB {method} {path}: HTTP {e.code} — {err_body}") from e

    # --- CRUD ---

    def get(self, collection: str, record_id: str) -> dict | None:
        try:
            return self._req("GET", f"/api/collections/{collection}/records/{record_id}")
        except RuntimeError as e:
            if "HTTP 404" in str(e):
                return None
            raise

    def get_one(self, collection: str, filter_str: str) -> dict | None:
        qs = urllib.parse.urlencode({"filter": filter_str, "perPage": 1})
        result = self._req("GET", f"/api/collections/{collection}/records?{qs}")
        items = result.get("items", [])
        return items[0] if items else None

    def get_list(self, collection: str, filter_str: str = "", per_page: int = 500, sort: str = "", **kwargs) -> list[dict]:
        if not filter_str and "filter" in kwargs:
            filter_str = kwargs["filter"]
        params: dict = {"filter": filter_str, "perPage": per_page}
        if sort:
            params["sort"] = sort
        qs = urllib.parse.urlencode(params)
        result = self._req("GET", f"/api/collections/{collection}/records?{qs}")
        return result.get("items", [])

    def create(self, collection: str, data: dict) -> dict:
        return self._req("POST", f"/api/collections/{collection}/records", data)

    def update(self, collection: str, record_id: str, data: dict) -> dict:
        return self._req("PATCH", f"/api/collections/{collection}/records/{record_id}", data)

    def delete(self, collection: str, record_id: str) -> None:
        self._req("DELETE", f"/api/collections/{collection}/records/{record_id}")

    # --- Jobs ---

    def get_job(self, job_id: Any) -> dict | None:
        return self.get("jobs", pad_id(job_id))

    def get_job_by_url(self, url: str) -> dict | None:
        safe = url.replace("'", "\\'")
        return self.get_one("jobs", f"url='{safe}'")

    def insert_job(self, **fields: Any) -> str:
        """Create job record. Returns PocketBase record ID."""
        rec = self.create("jobs", fields)
        return rec["id"]

    def update_job(self, job_id: Any, **fields: Any) -> None:
        self.update("jobs", pad_id(job_id), fields)

    def update_job_status(self, job_id: Any, status: str, comment: str | None = None) -> None:
        data: dict = {"status": status, "pipeline_status": status}
        if comment is not None:
            data["comment"] = comment
        self.update("jobs", pad_id(job_id), data)

    def soft_delete_job(self, job_id: Any) -> None:
        self.update("jobs", pad_id(job_id), {"deleted_at": _now_iso()})

    def get_dedup_keys(self, keys: list[str]) -> set[str]:
        """Return subset of keys already in DB."""
        if not keys:
            return set()
        filter_parts = " || ".join(
            f"dedup_key='{k.replace(chr(39), chr(92)+chr(39))}'" for k in keys
        )
        items = self.get_list("jobs", filter_parts, per_page=len(keys) + 10)
        return {r["dedup_key"] for r in items if r.get("dedup_key")}

    def get_existing_urls(self, urls: list[str]) -> set[str]:
        if not urls:
            return set()
        filter_parts = " || ".join(
            f"url='{u.replace(chr(39), chr(92)+chr(39))}'" for u in urls
        )
        items = self.get_list("jobs", filter_parts, per_page=len(urls) + 10)
        return {r["url"] for r in items if r.get("url")}

    # --- Companies ---

    def upsert_company(self, display_name: str, domain: str | None = None) -> str:
        normalized = re.sub(r"[^a-z0-9]", "", display_name.lower().strip())
        if domain:
            existing = self.get_one("companies", f"domain='{domain}'")
        else:
            existing = self.get_one("companies", f"normalized_name='{normalized}'")
        if existing:
            return existing["id"]
        rec = self.create("companies", {
            "display_name": display_name,
            "normalized_name": normalized,
            "domain": domain or "",
        })
        return rec["id"]

    # --- Job assessments ---

    def upsert_job_assessment(self, job_id: Any, **fields: Any) -> dict:
        pb_id = pad_id(job_id)
        existing = self.get_one("job_assessments", f"job_id='{pb_id}'")
        if existing:
            return self.update("job_assessments", existing["id"], fields)
        return self.create("job_assessments", {"job_id": pb_id, **fields})

    # --- Company research ---

    def upsert_company_research(self, company_id: Any, **fields: Any) -> dict | None:
        """Insert company research if none exists. Returns None if already present."""
        pb_id = pad_id(company_id)
        if self.get_one("company_research", f"company_id='{pb_id}'"):
            return None
        return self.create("company_research", {"company_id": pb_id, **fields})

    # --- Events ---

    def log_event(
        self,
        entity_type: str,
        entity_id: Any,
        event_type: str,
        actor: str = "system",
        event_json: str | None = None,
    ) -> None:
        self.create("events", {
            "entity_type": entity_type,
            "entity_id": pad_id(entity_id) if entity_id is not None else "",
            "event_type": event_type,
            "actor": actor,
            "event_json": event_json or "",
        })

    # --- Agent commands ---

    def get_command(self, command_id: Any) -> dict | None:
        return self.get("agent_commands", pad_id(command_id))

    def complete_command(
        self,
        command_id: Any,
        status: str,
        result_json: str | None = None,
        error: str | None = None,
    ) -> None:
        data: dict = {"status": status, "finished_at": _now_iso()}
        if result_json:
            data["result_json"] = result_json
        if error:
            data["error"] = error
        self.update("agent_commands", pad_id(command_id), data)

    def complete_pending_scrape_commands(self, job_id: Any, result_json: str) -> None:
        """Mark any pending/running scrape_job commands for this job as succeeded."""
        pb_id = pad_id(job_id)
        items = self.get_list(
            "agent_commands",
            f"command_type='scrape_job' && (status='pending' || status='running')",
            per_page=50,
        )
        for item in items:
            payload = item.get("payload_json") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            if str(payload.get("job_id", "")) in (str(job_id), pb_id):
                self.update("agent_commands", item["id"], {
                    "status": "succeeded",
                    "finished_at": _now_iso(),
                    "result_json": result_json,
                })

    # --- Pipeline runs ---

    def create_pipeline_run(self, run_type: str) -> str:
        rec = self.create("pipeline_runs", {"run_type": run_type, "status": "running"})
        return rec["id"]

    def finish_pipeline_run(
        self,
        run_id: Any,
        status: str,
        summary_json: str | None = None,
        error: str | None = None,
    ) -> None:
        data: dict = {"status": status, "finished_at": _now_iso()}
        if summary_json:
            data["summary_json"] = summary_json
        if error:
            data["error"] = error
        self.update("pipeline_runs", pad_id(run_id), data)


# Module-level singleton
_pb: PBClient | None = None


def get_pb() -> PBClient:
    global _pb
    if _pb is None:
        _pb = PBClient()
    return _pb
