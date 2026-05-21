from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ShallowJob:
    provider: str
    title: str
    company: str
    url: str
    location: str
    country: str | None
    dedup_key: str        # "{company}::{title}"
    posting_date: str | None
    salary_raw: str | None
    status: str = "listed"  # "listed" | "skip"


@dataclass
class HermesResult:
    success: bool
    data: dict
    error: str | None
    raw_output: str
