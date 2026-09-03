"""Offline tests. Nothing here touches the network except test_live_smoke,
which is skipped unless FDRATES_LIVE=1."""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from fdrates.models import COLUMNS, RATE_MAX, RATE_MIN, CustomerType, Status, load_banks
from fdrates.parse import looks_blocked, parse_html, parse_rate, parse_tenure
from fdrates.pipeline import collect_bank, run

FIXTURES = Path(__file__).parent / "fixtures"
SEED = Path(__file__).resolve().parents[1] / "data" / "seed" / "banks.csv"


# ------------------------------------------------------------------- tenure


@pytest.mark.parametrize(
    "label,expected",
    [
        ("7 days to 45 days", (7, 45)),
        ("7 - 14 days", (7, 14)),
        ("444 days", (444, 444)),
        ("1 year to less than 2 years", (365, 729)),
        ("211 days to less than 1 year", (211, 364)),
        ("5 years and above", (1825, None)),
        ("Above 1 year to 443 days", (366, 443)),
        ("15 months to 18 months", (450, 540)),
        ("1 year 11 months to 2 years", (695, 730)),
        ("Upto 45 days", (0, 45)),
        ("12 months", (360, 360)),
        ("", (None, None)),
        ("Special deposit scheme", (None, None)),
    ],
)
def test_parse_tenure(label, expected):
    assert parse_tenure(label) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("7.25", 7.25), ("7.25%", 7.25), ("6.50 % p.a.", 6.50),
        ("-", None), ("NA", None), ("", None),
        ("444", None),      # a tenure, not a rate
        ("2026", None),     # a year, not a rate
        ("0.10", None),     # below the plausible floor
    ],
)
def test_parse_rate(text, expected):
    assert parse_rate(text) == expected


def test_rate_bounds_are_enforced():
    assert parse_rate(str(RATE_MIN)) == RATE_MIN
    assert parse_rate(str(RATE_MAX)) == RATE_MAX
    assert parse_rate(str(RATE_MAX + 0.01)) is None


# ---------------------------------------------------------------- fixtures


def _fixture(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def test_simple_general_and_senior_table():
    rows = parse_html(_fixture("state_bank_of_india"))
    general = [r for r in rows if r.customer_type == CustomerType.GENERAL]
    senior = [r for r in rows if r.customer_type == CustomerType.SENIOR]
    assert len(general) == 8 and len(senior) == 8
    five_yr = [r for r in general if r.tenure_label.startswith("5 years")][0]
    assert five_yr.rate_pct == 6.05
    assert five_yr.tenure_days_max is None


def test_yield_column_is_not_mistaken_for_a_rate():
    rows = parse_html(_fixture("punjab_national_bank"))
    assert {r.customer_type for r in rows} == {CustomerType.GENERAL, CustomerType.SENIOR}
    assert 7.19 not in {r.rate_pct for r in rows}  # annualised yield column
    assert any(r.tenure_label == "444 days" and r.rate_pct == 7.25 for r in rows)


def test_multiple_amount_bands_and_navigation_table_ignored():
    rows = parse_html(_fixture("hdfc_bank_ltd"))
    bands = {r.deposit_band for r in rows}
    assert any("3 crore" in b.lower() for b in bands)
    assert any("5 crore" in b.lower() for b in bands)
    assert all(r.rate_pct is not None for r in rows)
    assert len(rows) == 16  # 5 + 3 tenures, two customer types each


def test_amount_band_columns_are_kept_as_general():
    rows = parse_html(_fixture("icici_bank_ltd"))
    general = [r for r in rows if r.customer_type == CustomerType.GENERAL]
    senior = [r for r in rows if r.customer_type == CustomerType.SENIOR]
    assert len(general) == 10  # two band columns x five tenures
    assert len(senior) == 5
    assert {r.deposit_band for r in general} == {
        "Below Rs. 3 crore", "Rs. 3 crore to Rs. 5 crore"}


def test_single_rate_column_bank():
    rows = parse_html(_fixture("hsbc_ltd"))
    assert len(rows) == 4
    assert {r.customer_type for r in rows} == {CustomerType.GENERAL}


def test_awkward_tenure_labels_survive_verbatim():
    rows = parse_html(_fixture("standard_chartered_bank_ltd"))
    labels = {r.tenure_label for r in rows}
    assert "1 year 11 months to 2 years" in labels
    assert "5 years and above" in labels
    assert any(r.tenure_days_min == 375 and r.tenure_days_max == 375 for r in rows)


def test_super_senior_column_detected():
    rows = parse_html(_fixture("jana_small_finance_bank_ltd"))
    assert {r.customer_type for r in rows} == {
        CustomerType.GENERAL, CustomerType.SENIOR, CustomerType.SUPER_SENIOR}
    assert max(r.rate_pct for r in rows) == 8.95


def test_positional_fallback_without_table_headers():
    rows = parse_html(_fixture("ujjivan_small_finance_bank_ltd"))
    assert len(rows) == 8
    assert any(r.rate_pct == 8.25 and r.customer_type == CustomerType.GENERAL for r in rows)


def test_bot_wall_is_recognised():
    assert looks_blocked(_fixture("south_indian_bank_ltd")) is not None
    assert looks_blocked(_fixture("state_bank_of_india")) is None


# ------------------------------------------------------------ seed + schema


def test_seed_list_loads_and_slugs_are_unique():
    banks = load_banks(SEED)
    assert len(banks) >= 50
    assert len({b.slug for b in banks}) == len(banks)


def test_every_bank_yields_at_least_one_row(tmp_path):
    banks = load_banks(SEED)
    rows = []
    for bank in banks:
        produced = collect_bank(bank, None, tmp_path, offline_dir=FIXTURES)
        assert produced, f"{bank.name} produced no rows"
        rows.extend(produced)
    assert {r.bank.name for r in rows} == {b.name for b in banks}


def test_status_semantics(tmp_path):
    banks = {b.slug: b for b in load_banks(SEED)}

    ok = collect_bank(banks["state_bank_of_india"], None, tmp_path, offline_dir=FIXTURES)
    assert all(r.status == Status.OK and r.rate_pct is not None for r in ok)

    blocked = collect_bank(banks["south_indian_bank_ltd"], None, tmp_path, offline_dir=FIXTURES)
    assert blocked[0].status == Status.BLOCKED and blocked[0].rate_pct is None

    no_fd = collect_bank(banks["barclays_bank_plc"], None, tmp_path, offline_dir=FIXTURES)
    assert no_fd[0].status == Status.NO_RETAIL_FD

    missing = collect_bank(banks["shivalik_small_finance_bank_ltd"], None, tmp_path,
                           offline_dir=FIXTURES)
    assert missing[0].status == Status.URL_MISSING


def test_written_csv_matches_the_published_schema(tmp_path):
    banks = load_banks(SEED)
    run(banks, out_root=tmp_path, offline_dir=FIXTURES)
    path = tmp_path / "latest" / "fd_rates.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == COLUMNS
        rows = list(reader)

    assert rows
    for row in rows:
        assert row["status"] in Status.ALL
        assert row["customer_type"] in CustomerType.ALL
        if row["status"] == Status.OK:
            assert row["rate_pct"], "an ok row must carry a rate"
            assert RATE_MIN <= float(row["rate_pct"]) <= RATE_MAX
            assert row["source_url"].startswith("http"), "an ok row must be verifiable"
            assert row["evidence_file"], "an ok row must point at a snapshot"
            assert row["tenure_label"]
        else:
            assert row["rate_pct"] == "", "a non-ok row must not carry a number"


def test_report_lists_every_bank_needing_a_manual_check(tmp_path):
    banks = load_banks(SEED)
    run(banks, out_root=tmp_path, offline_dir=FIXTURES)
    report = (tmp_path / "latest" / "run_report.md").read_text(encoding="utf-8")
    assert "Check these by hand" in report
    assert "South Indian Bank Ltd" in report
    assert "State Bank of India" not in report.split("Check these by hand")[1].split("##")[0]


# ------------------------------------------------------------------- live


@pytest.mark.skipif(os.environ.get("FDRATES_LIVE") != "1",
                    reason="live smoke test; set FDRATES_LIVE=1 to enable")
def test_live_smoke(tmp_path):
    banks = load_banks(SEED)[:5]
    summary = run(banks, out_root=tmp_path, dry_run=True)
    assert summary["banks_total"] == len(banks)
