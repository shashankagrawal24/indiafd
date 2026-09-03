"""Extraction layer: turn a rate page into RateRow objects.

Strategy: one generic table extractor is tried for every bank. Banks it gets
wrong get a per-bank override in fdrates/banks/. Parsing is deliberately
conservative - anything ambiguous becomes None rather than a guess.

Approximation used for tenure ranges: 1 month = 30 days, 1 year = 365 days.
The verbatim tenure_label is always kept so a human can check the arithmetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .models import RATE_MAX, RATE_MIN, CustomerType

# ---------------------------------------------------------------- text helpers

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"), "-")
_UNIT_DAYS = {
    "d": 1, "day": 1, "days": 1,
    "m": 30, "mth": 30, "mths": 30, "month": 30, "months": 30,
    "y": 365, "yr": 365, "yrs": 365, "year": 365, "years": 365,
}
_QTY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(days?|d|months?|mths?|m|years?|yrs?|y)?\b")
_SPLIT_RE = re.compile(r"\s+to\s+|\s*-\s*|\s+upto\s+|\s+up\s+to\s+|\s*<\s*|\s+till\s+")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").translate(_DASHES)).strip()


def parse_rate(text: str) -> float | None:
    """Return a plausible percentage, else None. Never guesses."""
    t = clean(text).replace(",", "")
    if not t or t.lower() in {"-", "na", "n/a", "nil", "--"}:
        return None
    m = re.search(r"(\d{1,2}(?:\.\d{1,4})?)\s*%?", t)
    if not m:
        return None
    try:
        val = round(float(m.group(1)), 2)
    except ValueError:
        return None
    return val if RATE_MIN <= val <= RATE_MAX else None


def _part_to_days(part: str, inherited_unit: str | None = None) -> tuple[int | None, str | None]:
    """Sum every quantity in a fragment, e.g. '1 year 11 months' -> 695."""
    total, unit_seen = 0, None
    found = False
    for qty, unit in _QTY_RE.findall(part):
        unit = (unit or inherited_unit or "").lower()
        if unit not in _UNIT_DAYS:
            continue
        total += float(qty) * _UNIT_DAYS[unit]
        unit_seen = unit
        found = True
    return (int(round(total)) if found else None), unit_seen


def parse_tenure(label: str) -> tuple[int | None, int | None]:
    """'1 year to less than 2 years' -> (365, 729). Returns (None, None) if unclear."""
    t = clean(label).lower()
    if not t:
        return None, None
    t = t.replace("above", " above ").replace("&", " and ")
    t = re.sub(r"\s+", " ", t).strip()

    open_ended = bool(re.search(r"(and above|above|onwards|and more|\+$)", t))
    open_ended_leading = bool(re.match(r"^(above|more than|greater than|>)\b", t))

    parts = [p for p in _SPLIT_RE.split(t) if p.strip()]
    if not parts:
        return None, None

    # A bare left number inherits the unit from the right side: '7 - 14 days'.
    _, right_unit = _part_to_days(parts[-1]) if len(parts) > 1 else (None, None)

    if len(parts) == 1:
        days, _ = _part_to_days(parts[0])
        if days is None:
            return None, None
        if open_ended_leading:
            return days + 1, None
        if open_ended:
            return days, None
        if re.search(r"(less than|below|<)", t):
            return 0, max(days - 1, 0)  # exclusive
        if re.search(r"(upto|up to|till|maximum)", t):
            return 0, days  # inclusive
        return days, days

    lo, _ = _part_to_days(parts[0], inherited_unit=right_unit)
    hi, _ = _part_to_days(parts[-1])
    if lo is None and hi is None:
        return None, None
    if re.search(r"(less than|below)", parts[-1]) and hi is not None:
        hi -= 1
    if re.search(r"(above|more than)", parts[0]) and lo is not None:
        lo += 1
    if open_ended and hi is None:
        return lo, None
    return lo, hi


def looks_like_tenure(text: str) -> bool:
    t = clean(text).lower()
    if not t or len(t) > 90:
        return False
    if not re.search(r"\d", t):
        return False
    return bool(re.search(r"(day|month|year|yr|mth)s?\b", t))


# ------------------------------------------------------------ header handling

_TENURE_HDR = re.compile(r"(tenure|tenor|period|maturity|duration|slab|term|days)", re.I)
_SENIOR_HDR = re.compile(r"senior|60 years|above 60", re.I)
_SUPER_HDR = re.compile(r"(super senior|very senior|80 year|above 80)", re.I)
_GENERAL_HDR = re.compile(
    r"(general|public|regular|normal|resident|domestic|rate of interest|\broi\b|"
    r"below 60|non[- ]senior|card rate|interest rate)", re.I)
_BAND_HDR = re.compile(r"(crore|lakh|lacs?|\bcr\b|rs\.?|inr|₹|amount|below|upto|up to|<|>)", re.I)
_EXCLUDE_HDR = re.compile(
    r"(yield|annualis|annualiz|maturity value|amount payable|effective|"
    r"minimum deposit|penalty|nre|nro|fcnr)", re.I)
_BLOCK_MARKERS = (
    "just a moment", "attention required", "cf-browser-verification",
    "checking your browser", "cloudflare", "access denied", "radware",
    "request unsuccessful", "incapsula", "captcha",
)


def customer_type_for(header: str) -> str | None:
    h = clean(header)
    if not h:
        return None
    if _SUPER_HDR.search(h):
        return CustomerType.SUPER_SENIOR
    if _SENIOR_HDR.search(h):
        return CustomerType.SENIOR
    if _GENERAL_HDR.search(h) or re.search(r"%|p\.?a\.?", h, re.I):
        return CustomerType.GENERAL
    return None


def looks_blocked(html: str) -> str | None:
    """Return the marker if the body is a bot wall rather than a rate page."""
    low = (html or "")[:6000].lower()
    for marker in _BLOCK_MARKERS:
        if marker in low:
            return marker
    return None


# --------------------------------------------------------------- table engine


@dataclass
class ParsedRate:
    tenure_label: str
    tenure_days_min: int | None
    tenure_days_max: int | None
    deposit_band: str
    customer_type: str
    rate_pct: float


def _table_to_matrix(table) -> list[list[str]]:
    matrix = []
    for tr in table.find_all("tr"):
        cells = [clean(td.get_text(" ")) for td in tr.find_all(["th", "td"])]
        if cells:
            matrix.append(cells)
    return matrix


def _column_map(header: list[str], width: int) -> tuple[int | None, dict[int, str]]:
    tenure_idx = None
    for i, h in enumerate(header):
        if _TENURE_HDR.search(h or ""):
            tenure_idx = i
            break
    rate_cols: dict[int, str] = {}
    for i, h in enumerate(header):
        if i == tenure_idx or _EXCLUDE_HDR.search(h or ""):
            continue
        ct = customer_type_for(h or "")
        if ct:
            rate_cols[i] = ct
    return tenure_idx, rate_cols


def rows_from_matrix(matrix: list[list[str]], context_band: str = "") -> list[ParsedRate]:
    """Pull rates out of a 2D table. Header-driven, with positional fallback."""
    if len(matrix) < 2:
        return []
    width = max(len(r) for r in matrix)
    header = matrix[0] + [""] * (width - len(matrix[0]))
    tenure_idx, rate_cols = _column_map(header, width)

    body_start = 1
    if tenure_idx is None:
        # No usable header: assume col 0 is tenure if its cells look like tenures.
        col0 = [r[0] for r in matrix if r]
        if sum(looks_like_tenure(c) for c in col0) < max(2, len(col0) // 3):
            return []
        tenure_idx = 0
        body_start = 1 if not looks_like_tenure(matrix[0][0]) else 0

    body = matrix[body_start:]
    if not body:
        return []

    numeric_cols = []
    for i in range(width):
        if i == tenure_idx or _EXCLUDE_HDR.search(header[i] if i < len(header) else ""):
            continue
        vals = [parse_rate(r[i]) for r in body if i < len(r)]
        if sum(v is not None for v in vals) >= max(2, len(body) // 2):
            numeric_cols.append(i)

    if not rate_cols:
        # No usable headers: leftmost numeric column is general, then senior.
        order = [CustomerType.GENERAL, CustomerType.SENIOR, CustomerType.SUPER_SENIOR]
        rate_cols = {c: order[min(n, 2)] for n, c in enumerate(numeric_cols)}
    else:
        # Headers named some columns but not all. Amount-band columns ("Below
        # Rs 3 crore" / "3-5 crore") are general rates and must not be dropped.
        for c in numeric_cols:
            if c not in rate_cols:
                rate_cols[c] = CustomerType.GENERAL

    band_by_col: dict[int, str] = {}
    for i, h in enumerate(header):
        if i in rate_cols and _BAND_HDR.search(h or ""):
            band_by_col[i] = clean(h)

    out: list[ParsedRate] = []
    for row in body:
        if tenure_idx >= len(row):
            continue
        label = row[tenure_idx]
        if not looks_like_tenure(label):
            continue
        lo, hi = parse_tenure(label)
        for col, ctype in rate_cols.items():
            if col >= len(row):
                continue
            rate = parse_rate(row[col])
            if rate is None:
                continue
            out.append(
                ParsedRate(
                    tenure_label=label,
                    tenure_days_min=lo,
                    tenure_days_max=hi,
                    deposit_band=band_by_col.get(col, context_band),
                    customer_type=ctype,
                    rate_pct=rate,
                )
            )
    return out


def _band_context(table) -> str:
    """Nearest preceding heading/caption that names a deposit amount band."""
    cap = table.find("caption")
    if cap and _BAND_HDR.search(cap.get_text(" ")):
        return clean(cap.get_text(" "))[:120]
    node = table
    for _ in range(6):
        node = node.find_previous(["h1", "h2", "h3", "h4", "h5", "p", "strong", "b"])
        if node is None:
            break
        text = clean(node.get_text(" "))
        if text and _BAND_HDR.search(text) and len(text) < 120:
            return text
    return ""


def parse_html(html: str, max_rows: int = 400) -> list[ParsedRate]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    results: list[ParsedRate] = []
    for table in soup.find_all("table"):
        matrix = _table_to_matrix(table)
        rows = rows_from_matrix(matrix, context_band=_band_context(table))
        if len(rows) >= 2:  # a single stray row is usually noise
            results.extend(rows)
        if len(results) >= max_rows:
            break
    return _dedupe(results)[:max_rows]


def parse_pdf(pdf_bytes: bytes, max_rows: int = 400) -> list[ParsedRate]:
    import io

    import pdfplumber

    results: list[ParsedRate] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                matrix = [[clean(c or "") for c in row] for row in table if row]
                rows = rows_from_matrix(matrix)
                if len(rows) >= 2:
                    results.extend(rows)
            if len(results) >= max_rows:
                break
    return _dedupe(results)[:max_rows]


def _dedupe(rows: list[ParsedRate]) -> list[ParsedRate]:
    seen, out = set(), []
    for r in rows:
        key = (r.tenure_label.lower(), r.customer_type, r.deposit_band.lower(), r.rate_pct)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
