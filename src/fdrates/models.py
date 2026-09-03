"""Data model and CSV schema for the FD rates pipeline."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))

# The published CSV schema. Order is part of the contract - tests enforce it.
COLUMNS = [
    "run_date",
    "bank_name",
    "category",
    "tenure_label",
    "tenure_days_min",
    "tenure_days_max",
    "deposit_band",
    "customer_type",
    "rate_pct",
    "source_url",
    "source_type",
    "fetched_at_ist",
    "status",
    "evidence_file",
    "notes",
]

# Plausible band for an Indian retail FD rate. Anything outside is not a rate.
RATE_MIN = 0.50
RATE_MAX = 12.00


class Status:
    OK = "ok"
    BLOCKED = "blocked"
    PARSE_FAILED = "parse_failed"
    URL_MISSING = "url_missing"
    NO_RETAIL_FD = "no_retail_fd"
    STALE_PARSER = "stale_parser"

    ALL = {OK, BLOCKED, PARSE_FAILED, URL_MISSING, NO_RETAIL_FD, STALE_PARSER}


class CustomerType:
    GENERAL = "general"
    SENIOR = "senior"
    SUPER_SENIOR = "super_senior"

    ALL = {GENERAL, SENIOR, SUPER_SENIOR}


class SourceType:
    HTML = "html"
    JS = "js"
    PDF = "pdf"
    NONE = "none"


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


@dataclass
class Bank:
    sr_no: str
    category: str
    name: str
    website: str
    rate_url: str
    page_format: str
    verification_status: str
    notes: str

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def source_type(self) -> str:
        pf = (self.page_format or "").strip().lower()
        if pf.startswith("pdf"):
            return SourceType.PDF
        if "js" in pf:
            return SourceType.JS
        if pf.startswith("html"):
            return SourceType.HTML
        return SourceType.NONE

    @property
    def has_retail_fd(self) -> bool:
        return "no retail fd" not in (self.verification_status or "").strip().lower()


@dataclass
class RateRow:
    """One (bank x tenure x customer type) observation, or one status row."""

    bank: Bank
    tenure_label: str = ""
    tenure_days_min: int | None = None
    tenure_days_max: int | None = None
    deposit_band: str = ""
    customer_type: str = CustomerType.GENERAL
    rate_pct: float | None = None
    fetched_at_ist: str = ""
    status: str = Status.OK
    evidence_file: str = ""
    notes: str = ""
    source_url_override: str | None = None
    extras: dict = field(default_factory=dict)

    def to_csv_row(self, run_date: str) -> dict:
        return {
            "run_date": run_date,
            "bank_name": self.bank.name,
            "category": self.bank.category,
            "tenure_label": self.tenure_label,
            "tenure_days_min": "" if self.tenure_days_min is None else self.tenure_days_min,
            "tenure_days_max": "" if self.tenure_days_max is None else self.tenure_days_max,
            "deposit_band": self.deposit_band,
            "customer_type": self.customer_type,
            "rate_pct": "" if self.rate_pct is None else f"{self.rate_pct:.2f}",
            "source_url": self.source_url_override or self.bank.rate_url,
            "source_type": self.bank.source_type,
            "fetched_at_ist": self.fetched_at_ist,
            "status": self.status,
            "evidence_file": self.evidence_file,
            "notes": self.notes,
        }


def load_banks(path: str | Path) -> list[Bank]:
    """Read the seed CSV. Column names come straight from the curated file."""
    banks: list[Bank] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if not (row.get("Bank Name") or "").strip():
                continue
            banks.append(
                Bank(
                    sr_no=(row.get("Sr No") or "").strip(),
                    category=(row.get("Category") or "").strip(),
                    name=(row.get("Bank Name") or "").strip(),
                    website=(row.get("Website (current)") or "").strip(),
                    rate_url=(row.get("FD Interest Rate Page") or "").strip(),
                    page_format=(row.get("Page Format") or "").strip(),
                    verification_status=(row.get("Verification Status") or "").strip(),
                    notes=(row.get("Notes") or "").strip(),
                )
            )
    return banks


def now_ist() -> datetime:
    return datetime.now(IST)


def write_csv(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
