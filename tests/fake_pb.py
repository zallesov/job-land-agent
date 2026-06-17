"""In-memory PocketBase double for tests.

Overrides only the low-level CRUD primitives of PBClient (get/get_one/get_list/
create/update/delete). All higher-level methods (insert_job, get_dedup_keys,
upsert_company, ...) are inherited unchanged from PBClient and run against the
in-memory store. Never touches the network or any real PocketBase instance.
"""
from __future__ import annotations

import re
from typing import Any

from scripts.pb_client import PBClient


def _matches(filter_str: str, record: dict) -> bool:
    if not filter_str:
        return True

    def repl(m: re.Match) -> str:
        field, value = m.group(1), m.group(2).replace("\\'", "'")
        return "True" if str(record.get(field, "")) == value else "False"

    expr = re.sub(r"(\w+)='((?:[^'\\]|\\.)*)'", repl, filter_str)
    expr = expr.replace("&&", " and ").replace("||", " or ")
    return eval(expr, {"__builtins__": {}}, {})  # noqa: S307 — trusted, internally-generated expr


class FakePBClient(PBClient):
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict]] = {}
        self._counters: dict[str, int] = {}

    def _next_id(self, collection: str) -> str:
        self._counters[collection] = self._counters.get(collection, 0) + 1
        return f"fake{self._counters[collection]:011d}"

    def get(self, collection: str, record_id: str) -> dict | None:
        return self.collections.get(collection, {}).get(record_id)

    def get_one(self, collection: str, filter_str: str) -> dict | None:
        for rec in self.collections.get(collection, {}).values():
            if _matches(filter_str, rec):
                return rec
        return None

    def get_list(self, collection: str, filter_str: str = "", per_page: int = 500, sort: str = "", **kwargs: Any) -> list[dict]:
        if not filter_str and "filter" in kwargs:
            filter_str = kwargs["filter"]
        items = [r for r in self.collections.get(collection, {}).values() if _matches(filter_str, r)]
        return items[:per_page]

    def create(self, collection: str, data: dict) -> dict:
        rid = data.get("id") or self._next_id(collection)
        rec = {"id": rid, **data}
        self.collections.setdefault(collection, {})[rid] = rec
        return rec

    def update(self, collection: str, record_id: str, data: dict) -> dict:
        rec = self.collections.setdefault(collection, {}).setdefault(record_id, {"id": record_id})
        rec.update(data)
        return rec

    def delete(self, collection: str, record_id: str) -> None:
        self.collections.get(collection, {}).pop(record_id, None)
