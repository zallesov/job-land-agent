#!/usr/bin/env python3
"""Migrate old contacts/telegram_handle fields → contacts_json array."""

import sqlite3
import json
import re

DB = "/Users/zall/.hermes/profiles/joblandagent-dev/jobs.db"

def parse_contacts_text(text: str, telegram_handle: str = "") -> list[dict]:
    """Parse freeform contacts text into [{name, email, telegram, ...}] array."""
    contacts = []

    if text:
        # Split on ' | ' separator first
        parts = re.split(r"\s*\|\s*", text)

        # If single part with commas and no angle brackets — check if multiple emails or names
        if len(parts) == 1 and "," in text and "<" not in text:
            if "@" in text:
                # Multiple plain emails: "a@x.com,b@x.com"
                parts = [p.strip() for p in text.split(",")]
            else:
                # Multiple names: "Egor Spirin, Bradley Kearsley"
                parts = [p.strip() for p in text.split(",")]

        for part in parts:
            part = part.strip()
            if not part:
                continue

            contact: dict = {}

            # "Name <value> - optional note" pattern
            m = re.match(r"^(.+?)\s*<([^>]+)>\s*(?:-\s*(.+))?$", part)
            if m:
                name_raw = m.group(1).strip()
                value = m.group(2).strip()
                note = (m.group(3) or "").strip()

                if name_raw:
                    contact["name"] = name_raw
                if value.startswith("@"):
                    contact["telegram"] = value
                elif "@" in value:
                    contact["email"] = value
                else:
                    contact["other"] = value
                if note and note.lower() not in ("telegram",):
                    contact["note"] = note

            elif "@" in part and "<" not in part:
                # Plain email address
                contact["email"] = part.strip()

            else:
                # May contain @telegram handle inline
                tg_match = re.search(r"@\w+", part)
                if tg_match:
                    remainder = re.sub(r"\s*-?\s*telegram\s*", "", part, flags=re.I).strip()
                    remainder = remainder.replace(tg_match.group(0), "").strip(" -")
                    if remainder:
                        contact["name"] = remainder
                    contact["telegram"] = tg_match.group(0)
                else:
                    contact["name"] = part

            if contact:
                contacts.append(contact)

    # Merge telegram_handle into first contact, or add standalone
    if telegram_handle:
        tg = telegram_handle if telegram_handle.startswith("@") else f"@{telegram_handle}"
        if contacts:
            contacts[0].setdefault("telegram", tg)
        else:
            contacts.append({"telegram": tg})

    return contacts


def main():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        "SELECT id, contacts, telegram_handle, contact_via, contacts_json FROM interviews"
    ).fetchall()

    updated = 0
    for row in rows:
        rid = row["id"]
        old_contacts = row["contacts"] or ""
        telegram = row["telegram_handle"] or ""

        if not old_contacts and not telegram:
            print(f"  [{rid}] nothing to migrate — skip")
            continue

        parsed = parse_contacts_text(old_contacts, telegram)
        if not parsed:
            print(f"  [{rid}] parse returned empty — skip")
            continue

        new_json = json.dumps(parsed, ensure_ascii=False)
        db.execute(
            "UPDATE interviews SET contacts_json = ? WHERE id = ?",
            (new_json, rid),
        )
        print(f"  [{rid}] {new_json}")
        updated += 1

    db.commit()
    db.close()
    print(f"\nDone — migrated {updated} rows.")


if __name__ == "__main__":
    main()
