#!/usr/bin/env python3
"""Drop unused columns from job_assessments. Run after research_job.py is updated."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db import get_connection

DB_PATH = str(Path(__file__).parent.parent / "jobs.db")

COLUMNS_TO_DROP = [
    "ic_or_management",
    "visa_contract_structure",
    "ai_native_assessment",
    "assessment_notes",
    "source_urls_json",
    "raw_assessment_json",
]


def migrate(db_path: str = DB_PATH) -> None:
    con = get_connection(db_path)
    try:
        for col in COLUMNS_TO_DROP:
            try:
                con.execute(f"ALTER TABLE job_assessments DROP COLUMN {col}")
                print(f"Dropped: {col}")
            except Exception as e:
                print(f"Skipped {col}: {e}")
        con.commit()
        print("Column drop complete.")
    finally:
        con.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DB_PATH)
    args = p.parse_args()
    migrate(args.db)
