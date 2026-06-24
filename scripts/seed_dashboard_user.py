#!/usr/bin/env python3
"""
Seed the dashboard auth admin user and lock app collections.

Part of the dashboard-auth security feature
(docs/superpowers/specs/2026-06-24-dashboard-auth-design.md).

What it does (idempotent, re-runnable on a fresh DB):
  1. Ensures a `users` auth collection exists (PocketBase v0.27). Creates it as
     type "auth" if missing — system fields (id, email, password, ...) are
     auto-populated by PocketBase.
  2. Upserts ONE admin user in `users` from env:
       ADMIN_EMAIL    (default admin@joblandagent.local)
       ADMIN_PASSWORD (default joblandzi!1a)
     Looked up by email; if present, its password is reset instead of failing.
  3. Locks API rules (list/view/create/update/delete) to
     `@request.auth.id != ""` on: jobs, job_assessments, company_research,
     agent_commands, interviews, events. Missing collections are skipped with
     a warning.

Uses the superuser PBClient from scripts/pb_client.py (stdlib only).

Usage:
  python3 scripts/seed_dashboard_user.py

Env (consumed in addition to POCKETBASE_* used by pb_client):
  ADMIN_EMAIL, ADMIN_PASSWORD
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pb_client import get_pb  # noqa: E402

DEFAULT_ADMIN_EMAIL = "admin@joblandagent.local"
DEFAULT_ADMIN_PASSWORD = "joblandzi!1a"

USERS_COLLECTION = "users"

# Collections to lock to authenticated-only access.
LOCKED_COLLECTIONS = [
    "jobs",
    "job_assessments",
    "company_research",
    "agent_commands",
    "interviews",
    "events",
]

AUTH_RULE = '@request.auth.id != ""'

RULE_FIELDS = ["listRule", "viewRule", "createRule", "updateRule", "deleteRule"]


def ensure_users_collection(pb) -> str:
    """Ensure the `users` auth collection exists. Returns 'created' | 'exists'."""
    existing = pb.get_collection(USERS_COLLECTION)
    if existing is not None:
        if existing.get("type") != "auth":
            raise SystemExit(
                f"FATAL: collection '{USERS_COLLECTION}' exists but is type "
                f"'{existing.get('type')}', expected 'auth'."
            )
        return "exists"

    # Minimal create payload — PocketBase v0.27 auto-populates the auth system
    # fields (id, email, password, tokenKey, emailVisibility, verified, ...).
    pb.create_collection(
        {
            "name": USERS_COLLECTION,
            "type": "auth",
            "passwordAuth": {"enabled": True, "identityFields": ["email"]},
        }
    )
    return "created"


def upsert_admin_user(pb, email: str, password: str) -> str:
    """Create or update the single admin user. Returns 'created' | 'updated'."""
    safe_email = email.replace("'", "\\'")
    existing = pb.get_one(USERS_COLLECTION, f"email='{safe_email}'")
    payload = {
        "email": email,
        "password": password,
        "passwordConfirm": password,
        "verified": True,
    }
    if existing:
        # Reset password + ensure verified; don't resend email change, keep email.
        pb.update(USERS_COLLECTION, existing["id"], {
            "password": password,
            "passwordConfirm": password,
            "verified": True,
        })
        return "updated"
    pb.create(USERS_COLLECTION, payload)
    return "created"


def lock_collection(pb, name: str) -> str:
    """Set authenticated-only API rules. Returns 'locked' | 'missing' | 'unchanged'."""
    coll = pb.get_collection(name)
    if coll is None:
        return "missing"

    already = all(coll.get(f) == AUTH_RULE for f in RULE_FIELDS)
    if already:
        return "unchanged"

    pb.update_collection(name, {f: AUTH_RULE for f in RULE_FIELDS})
    return "locked"


def main() -> int:
    email = os.environ.get("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)
    password = os.environ.get("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)

    pb = get_pb()

    print(f"PocketBase: {pb._base}")  # noqa: SLF001 — informational only
    print("=" * 60)

    # 1. users auth collection
    users_state = ensure_users_collection(pb)
    if users_state == "created":
        print(f"[users] created auth collection '{USERS_COLLECTION}'")
    else:
        print(f"[users] auth collection '{USERS_COLLECTION}' already exists")

    # 2. admin user
    user_state = upsert_admin_user(pb, email, password)
    if user_state == "created":
        print(f"[user]  created admin user {email}")
    else:
        print(f"[user]  admin user {email} already existed — password reset")

    # 3. lock collections
    print("-" * 60)
    locked, unchanged, missing = [], [], []
    for name in LOCKED_COLLECTIONS:
        state = lock_collection(pb, name)
        if state == "locked":
            locked.append(name)
            print(f"[rules] {name}: locked to {AUTH_RULE}")
        elif state == "unchanged":
            unchanged.append(name)
            print(f"[rules] {name}: already locked (unchanged)")
        else:  # missing
            missing.append(name)
            print(f"[rules] {name}: WARNING collection not found — skipped")

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print(f"  users collection : {users_state}")
    print(f"  admin user       : {email} ({user_state})")
    print(f"  rules locked     : {locked or '-'}")
    print(f"  rules unchanged  : {unchanged or '-'}")
    if missing:
        print(f"  rules MISSING    : {missing}  (these collections were not found)")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
