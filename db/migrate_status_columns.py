#!/usr/bin/env python3
"""
One-time migration: split jobs.status into pipeline_status / user_status / research_status.
Safe to run multiple times (ALTER TABLE skipped if column exists).
"""
import sqlite3, sys
from pathlib import Path

DB = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "jobs.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Add columns if missing
existing = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
for alter_sql in [
    "ALTER TABLE jobs ADD COLUMN pipeline_status TEXT NOT NULL DEFAULT 'new'",
    "ALTER TABLE jobs ADD COLUMN user_status TEXT",
    "ALTER TABLE jobs ADD COLUMN research_status TEXT",
]:
    col_name = alter_sql.split("ADD COLUMN ")[1].split()[0]
    if col_name not in existing:
        con.execute(alter_sql)
        print(f"Added column {col_name}")

# Migrate pipeline statuses
con.execute("""
    UPDATE jobs SET pipeline_status = status
    WHERE status IN ('new','enriched','screened','enrich_failed','screen_failed')
    AND pipeline_status = 'new'
""")
# researched → pipeline stays screened, research_status = 'researched'
con.execute("""
    UPDATE jobs SET pipeline_status = 'screened', research_status = 'researched'
    WHERE status = 'researched'
""")
# User statuses: pipeline unknown — best guess is 'screened' (was visible/actioned)
con.execute("""
    UPDATE jobs SET
        user_status = status,
        pipeline_status = 'screened'
    WHERE status IN ('interesting','not_interesting','applied','rejected',
                     'interviewing','draft_ready','archived','offer')
""")

# Create indexes on new columns
con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_pipeline_status ON jobs(pipeline_status)")
con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_status)")
con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_research_status ON jobs(research_status)")

con.commit()

# Print summary
print("\nDistribution after migration:")
for row in con.execute("""
    SELECT pipeline_status, user_status, research_status, count(*) n
    FROM jobs WHERE deleted_at IS NULL
    GROUP BY 1,2,3 ORDER BY n DESC
"""):
    print(dict(row))

con.close()
print("\nMigration complete.")
