#!/usr/bin/env python3
"""
Shared job sanity filter for all scrapers.

Filters out jobs that don't match the user's profile:
- Principal AI/Cloud Engineer (~20yr experience)
- Looking for senior/principal/staff level engineering roles
- Focus: AI/ML, backend, platform, infrastructure, distributed systems
- Locations: remote (EU), Berlin, Spain

Use is_relevant(job_title, job_location, job_description) before adding a job.
"""

import re

# Titles that are clearly NOT relevant — no technical engineering
IRRELEVANT_TITLE_PATTERNS = [
    # Analyst / strategy / marketing / sales
    r"analyst",
    r"strategist",
    r"strategy",
    r"marketing",
    r"sales\b",
    r"business development",
    r"account (manager|executive)",
    r"customer success",
    r"customer support",
    r"support engineer",  # not the same as infra/platform engineer
    r"brand ",
    r"partner(ship)? ",
    r"recruiter",
    r"hr ",
    r"people ",
    r"talent ",
    r"finance",
    r"accounting",
    r"controller",
    r"audit",
    r"legal",
    r"compliance",
    r"risk ",
    r"underwriter",
    r"content",
    r"writer",
    r"editor",
    r"social media",
    r"community ",
    r"event",
    r"office ",
    r"administrat",
    r"operations(\s|$)",  # "Operations Manager" ≠ engineering
    r"supply chain",
    r"logistics",
    r"procurement",
    r"manufacturing",
    r"quality (assurance|engineer)",  # QA is not the target
    r"\bqa(\s|$)",
    r"\btest(\s|$)",  # "test engineer", "test automation"
    r"manual ",
    r"designer",
    r"design ",
    r"art ",
    r"creative",
    r"visual",
    r"ui(\s|$)",  # UI/UX not relevant
    r"ux ",
    r"graphic",
    r"motion",
    r"video",
    r"media ",
    r"medical",
    r"clinical",
    r"pharma",
    r"biolog",
    r"chemist",
    r"nurse",
    r"doctor",
    r"physician",
    r"teacher",
    r"professor",
    r"instructor",
    r"coach",
    r"psycholog",
    r"therapist",
    r"social work",
    r"hospitality",
    r"chef",
    r"cook",
    r"server",
    r"bartender",
    r"driver",
    r"delivery",
    r"warehouse",
    r"janitor",
    r"cleaner",
    r"maintenance",
    r"security (guard|officer)",
    r"receptionist",
    r"assistant",
    r"coordinator",
    r"intern",
    r"trainee",
    r"graduate",
    r"junior",
    r"\bentry\b",
    r"\bjr\b",
]

# Title patterns that are RELEVANT (overrides irrelevant if matched)
RELEVANT_TITLE_PATTERNS = [
    r"staff (software|engineer)",
    r"principal (software|engineer|architect|ai|ml)",
    r"distinguished",
    r"fellow",
    r"head of (engineering|ai|ml|platform|infra|technology)",
    r"vp of (engineering|ai|ml|platform|infra|technology)",
    r"director of (engineering|ai|ml|platform|infra|technology)",
    r"engineering (manager|director|lead|leader)",
    r"team (lead|leader)",
    r"product (manager|director|lead)",
    r"tech lead",
    r"lead (software|engineer|backend|frontend|platform|infra|ai|ml)",
    r"senior (software|engineer|backend|frontend|full.?stack|platform|infra|devops|sre|ai|ml|data|research)",
    r"staff (software|engineer|backend|frontend|platform|infra|sre|ai|ml)",
    r"principal (software|engineer|backend|frontend|platform|infra|sre|ai|ml)",
    r"architect",
    r"machine learning (engineer|lead|manager|director)",
    r"ai (engineer|lead|manager|director|architect)",
    r"ml (engineer|lead|manager|director|ops)",
    r"data (engineer|architect|platform)",
    r"backend (engineer|developer|lead|manager)",
    r"frontend (engineer|developer|lead|manager|architect)",
    r"full.?stack (engineer|developer|lead|manager)",
    r"platform (engineer|lead|manager|architect)",
    r"infrastructure (engineer|lead|manager|architect)",
    r"devops (engineer|lead|manager)",
    r"sre (engineer|lead|manager)",
    r"site reliability",
    r"software (engineer|developer|architect)",
    r"systems (engineer|architect)",
    r"cloud (engineer|architect|lead)",
    r"research (engineer|scientist)",
    r"applied (scientist|researcher|engineer)",
    r"\bscientist(\s|$)",  # "Data Scientist", "Applied Scientist"
    r"software (engineer|developer)",
]

# Compile once
_irrelevant_re = re.compile(
    "|".join(IRRELEVANT_TITLE_PATTERNS), re.IGNORECASE
)
_relevant_re = re.compile(
    "|".join(RELEVANT_TITLE_PATTERNS), re.IGNORECASE
)


def is_relevant(job: dict) -> bool:
    """Return True if this job should be kept, False to filter out."""
    title = (job.get("title") or "").strip()
    if not title:
        return False

    # Check if the title matches any relevant pattern
    has_relevant = bool(_relevant_re.search(title))
    has_irrelevant = bool(_irrelevant_re.search(title))

    # If title matches both relevant AND irrelevant, prefer relevant
    # (e.g. "Senior Software Engineer, AI" matches "senior software engineer" → relevant,
    #  even if "engineer" might match something weird)
    # EXCEPT: "intern", "junior", "trainee", "graduate" override even relevant titles
    _overrides_relevant = re.search(r"\bintern\b|\bjr\b|\bjunior\b|\btrainee\b|\bgraduate\b|entry.level", title, re.IGNORECASE)
    if _overrides_relevant and has_relevant:
        return False
    if has_relevant:
        return True

    # If title only matches irrelevant, reject
    if has_irrelevant:
        return False

    # If neither pattern matched, reject (too vague / not tech)
    return False
