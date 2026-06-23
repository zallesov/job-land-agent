from __future__ import annotations

"""csvfeed provider auth check.

CSV imports do not need a browser session, but the pipeline expects every
provider to expose a check_auth(cdp_url) function.
"""


def check_auth(cdp_url: str) -> bool:
    return True
