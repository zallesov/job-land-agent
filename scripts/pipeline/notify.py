from __future__ import annotations
import subprocess

HERMES = "hermes"
TELEGRAM_TARGET = "telegram"


def telegram_notify(message: str) -> None:
    subprocess.run(
        [HERMES, "send", "--to", TELEGRAM_TARGET, message],
        capture_output=True,
    )


def send_daily_digest(
    enrich_failures: list[tuple[int, str]] | None = None,
    sanity_failures: list[tuple[int, str]] | None = None,
) -> None:
    enrich_failures = enrich_failures or []
    sanity_failures = sanity_failures or []
    if not enrich_failures and not sanity_failures:
        return
    lines = ["Pipeline completed with failures"]
    if enrich_failures:
        lines.append(f"Enrich failed: {len(enrich_failures)} job(s)")
        for jid, err in enrich_failures[:5]:
            lines.append(f"  - job {jid}: {err[:60]}")
    if sanity_failures:
        lines.append(f"Sanity check failed: {len(sanity_failures)} job(s)")
        for jid, err in sanity_failures[:5]:
            lines.append(f"  - job {jid}: {err[:60]}")
    telegram_notify("\n".join(lines))
