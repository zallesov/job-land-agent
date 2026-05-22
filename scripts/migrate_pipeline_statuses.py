#!/usr/bin/env python3
"""
One-time migration: align jobs.status to new pipeline-stage values.
Run ONCE after all code is updated.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db import get_connection

DB_PATH = str(Path(__file__).parent.parent / "jobs.db")


def migrate(db_path: str = DB_PATH) -> None:
    con = get_connection(db_path)
    try:
        # listed → new (jobs that were never enriched)
        r = con.execute("UPDATE jobs SET status='new' WHERE status='listed'")
        print(f"listed → new: {r.rowcount} rows")

        # skip and not_interested → screened (verdict captured in apply_verdict)
        r = con.execute("UPDATE jobs SET status='screened' WHERE status IN ('skip','not_interested')")
        print(f"skip/not_interested → screened: {r.rowcount} rows")

        # sanity_failed → screen_failed
        r = con.execute("UPDATE jobs SET status='screen_failed' WHERE status='sanity_failed'")
        print(f"sanity_failed → screen_failed: {r.rowcount} rows")

        # Backfill job_assessments with apply_verdict=Skip for newly-screened jobs that have no assessment
        r = con.execute("""
            INSERT INTO job_assessments (job_id, assessment_status, apply_verdict, assessed_at)
            SELECT id, 'screened', 'Skip', datetime('now')
            FROM jobs
            WHERE status = 'screened'
              AND id NOT IN (
                SELECT job_id FROM job_assessments WHERE apply_verdict IS NOT NULL
              )
            ON CONFLICT(job_id) DO UPDATE
              SET apply_verdict = 'Skip', assessment_status = 'screened'
              WHERE job_assessments.apply_verdict IS NULL
        """)
        print(f"Backfilled Skip assessment: {r.rowcount} rows")

        # Migrate old apply_verdict 'Apply' → 'Strong Apply' (research_job used to emit 'Apply')
        r = con.execute(
            "UPDATE job_assessments SET apply_verdict='Strong Apply' WHERE apply_verdict='Apply'"
        )
        print(f"apply_verdict 'Apply' → 'Strong Apply': {r.rowcount} rows")

        # Normalize casing: 'Apply with caution' → 'Apply with Caution'
        r = con.execute(
            "UPDATE job_assessments SET apply_verdict='Apply with Caution' WHERE apply_verdict='Apply with caution'"
        )
        print(f"apply_verdict casing fix: {r.rowcount} rows")

        con.commit()
        print("Migration complete.")
    finally:
        con.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DB_PATH)
    args = p.parse_args()
    migrate(args.db)
