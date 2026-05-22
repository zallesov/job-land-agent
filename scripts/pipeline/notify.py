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
    screen_failures: list[tuple[int, str]] | None = None,
) -> None:
    enrich_failures = enrich_failures or []
    screen_failures = screen_failures or []
    if not enrich_failures and not screen_failures:
        return
    lines = ["Pipeline completed with failures"]
    if enrich_failures:
        lines.append(f"Enrich failed: {len(enrich_failures)} job(s)")
        for jid, err in enrich_failures[:5]:
            lines.append(f"  - job {jid}: {err[:60]}")
    if screen_failures:
        lines.append(f"Screen failed: {len(screen_failures)} job(s)")
        for jid, err in screen_failures[:5]:
            lines.append(f"  - job {jid}: {err[:60]}")
    telegram_notify("\n".join(lines))
