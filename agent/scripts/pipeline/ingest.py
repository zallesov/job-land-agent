from __future__ import annotations
from pathlib import Path
from .types import ShallowJob

_SKIP_COMMENT = "Auto-filtered by job_filter before research"


def ingest_jobs(jobs: list[ShallowJob]) -> list[str]:
    """Insert jobs into PocketBase. Returns IDs of non-skip jobs only."""
    if not jobs:
        return []

    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from scripts.pb_client import get_pb

    pb = get_pb()
    ids: list[str] = []
    for j in jobs:
        is_skip = j.status == "skip"
        try:
            rec_id = pb.insert_job(
                url=j.url or "",
                apply_url=j.url or "",
                provider=j.provider or "",
                posted_company_name=j.company or "",
                title=j.title or "",
                location=j.location or "",
                country=j.country or "",
                date_posted=j.posting_date or "",
                salary_range=j.salary_raw or "",
                dedup_key=j.dedup_key or "",
                status=j.status or "new",
                pipeline_status="new",
                comment=_SKIP_COMMENT if is_skip else "",
            )
            if not is_skip:
                ids.append(rec_id)
        except RuntimeError as e:
            if "unique" in str(e).lower() or "HTTP 400" in str(e):
                pass  # duplicate URL — skip silently
            else:
                raise
    return ids
