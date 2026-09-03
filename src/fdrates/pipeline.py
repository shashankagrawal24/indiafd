"""Run the whole collection: one bank at a time, failures isolated."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from .banks import get_override
from .fetch import Fetcher, Outcome, save_evidence
from .models import (
    Bank,
    CustomerType,
    RateRow,
    SourceType,
    Status,
    now_ist,
    write_csv,
)
from .parse import ParsedRate, looks_blocked, parse_html, parse_pdf

log = logging.getLogger("fdrates")


def _status_row(bank: Bank, status: str, note: str, ts: str,
                evidence: str = "", url: str | None = None) -> RateRow:
    return RateRow(
        bank=bank, customer_type=CustomerType.GENERAL, rate_pct=None,
        fetched_at_ist=ts, status=status, notes=note[:300],
        evidence_file=evidence, source_url_override=url,
    )


def _to_rows(bank: Bank, parsed: list[ParsedRate], ts: str,
             evidence: str, url: str, note: str = "") -> list[RateRow]:
    return [
        RateRow(
            bank=bank,
            tenure_label=p.tenure_label,
            tenure_days_min=p.tenure_days_min,
            tenure_days_max=p.tenure_days_max,
            deposit_band=p.deposit_band,
            customer_type=p.customer_type,
            rate_pct=p.rate_pct,
            fetched_at_ist=ts,
            status=Status.OK,
            evidence_file=evidence,
            notes=note,
            source_url_override=url,
        )
        for p in parsed
    ]


def collect_bank(bank: Bank, fetcher: Fetcher | None, evidence_dir: Path,
                 offline_dir: Path | None = None) -> list[RateRow]:
    """Always returns at least one row. Never raises."""
    ts = now_ist().isoformat(timespec="seconds")

    if not bank.has_retail_fd:
        return [_status_row(bank, Status.NO_RETAIL_FD,
                            bank.notes or "no retail term deposit product", ts)]
    if not bank.rate_url:
        return [_status_row(bank, Status.URL_MISSING,
                            bank.notes or "no FD rate page URL in seed list", ts)]

    try:
        # ---- offline mode: parse a committed snapshot instead of the live site
        if offline_dir is not None:
            snap = _find_snapshot(offline_dir, bank.slug)
            if snap is None:
                return [_status_row(bank, Status.BLOCKED,
                                    "offline mode: no local snapshot for this bank", ts)]
            out = Outcome(ok=True, content=snap.read_bytes(),
                          text="" if snap.suffix == ".pdf" else snap.read_text(
                              encoding="utf-8", errors="replace"),
                          url=bank.rate_url, http_status=200)
            evidence = str(snap)
            source_url = bank.rate_url
            note = "parsed from local snapshot"
            marker = looks_blocked(out.text) if out.text else None
            if marker:
                return [_status_row(bank, Status.BLOCKED,
                                    f"challenge page detected ({marker})",
                                    ts, evidence, source_url)]
        else:
            assert fetcher is not None
            source_url, note = bank.rate_url, ""
            if bank.source_type == SourceType.PDF:
                source_url, note = fetcher.resolve_pdf_url(bank.website, bank.rate_url)
                out = fetcher.get(source_url)
            elif bank.source_type == SourceType.JS:
                out = fetcher.get_rendered(bank.rate_url)
            else:
                out = fetcher.get(bank.rate_url)
            evidence = save_evidence(evidence_dir, bank.slug, out)

            log.info("%-42s %-6s %s", bank.slug, out.http_status or "-",
                     "ok" if out.ok else out.note[:60])

            if not out.ok:
                status = Status.BLOCKED if out.blocked else Status.PARSE_FAILED
                return [_status_row(bank, status, f"{note + '; ' if note else ''}{out.note}",
                                    ts, evidence, source_url)]

        # ---- parse
        override = get_override(bank.slug)
        if override is not None:
            parsed = override(out.text or out.content)
        elif out.is_pdf:
            parsed = parse_pdf(out.content)
        else:
            parsed = parse_html(out.text)

        if not parsed:
            return [_status_row(bank, Status.PARSE_FAILED,
                                "page fetched but no rate table recognised - "
                                "check the snapshot and add a per-bank parser",
                                ts, evidence, source_url)]
        return _to_rows(bank, parsed, ts, evidence, source_url, note)

    except Exception as exc:  # one bank must never take down the run
        log.exception("unhandled error for %s", bank.slug)
        return [_status_row(bank, Status.PARSE_FAILED,
                            f"{type(exc).__name__}: {str(exc)[:150]}", ts)]


def _find_snapshot(directory: Path, slug: str) -> Path | None:
    for ext in (".html", ".htm", ".pdf", ".txt"):
        candidate = directory / f"{slug}{ext}"
        if candidate.exists():
            return candidate
    return None


def run(banks: list[Bank], out_root: Path, offline_dir: Path | None = None,
        dry_run: bool = False, respect_robots: bool = True) -> dict:
    run_date = now_ist().date().isoformat()
    history_dir = out_root / "history" / run_date
    # --dry-run promises to write nothing into the repo, snapshots included.
    evidence_dir = (
        Path(tempfile.mkdtemp(prefix="fdrates-dryrun-")) if dry_run
        else history_dir / "evidence"
    )

    fetcher = None if offline_dir is not None else Fetcher(respect_robots=respect_robots)
    all_rows: list[RateRow] = []
    try:
        for bank in banks:
            all_rows.extend(collect_bank(bank, fetcher, evidence_dir, offline_dir))
    finally:
        if fetcher is not None:
            fetcher.close()

    csv_rows = [r.to_csv_row(run_date) for r in all_rows]
    summary = summarise(banks, all_rows, run_date)

    if not dry_run:
        write_csv(csv_rows, history_dir / "fd_rates.csv")
        write_csv(csv_rows, out_root / "latest" / "fd_rates.csv")
        report = build_report(banks, all_rows, summary)
        (out_root / "latest").mkdir(parents=True, exist_ok=True)
        (out_root / "latest" / "run_report.md").write_text(report, encoding="utf-8")
        (history_dir / "run_report.md").write_text(report, encoding="utf-8")
    return summary


def summarise(banks: list[Bank], rows: list[RateRow], run_date: str) -> dict:
    by_bank: dict[str, list[RateRow]] = {}
    for r in rows:
        by_bank.setdefault(r.bank.name, []).append(r)
    eligible = [b for b in banks if b.has_retail_fd and b.rate_url]
    ok = [name for name, rs in by_bank.items() if any(r.status == Status.OK for r in rs)]
    counts: dict[str, int] = {}
    for name, rs in by_bank.items():
        counts[rs[0].status if not any(r.status == Status.OK for r in rs) else Status.OK] = (
            counts.get(rs[0].status if not any(r.status == Status.OK for r in rs)
                       else Status.OK, 0) + 1)
    return {
        "run_date": run_date,
        "banks_total": len(banks),
        "banks_eligible": len(eligible),
        "banks_ok": len(ok),
        "rate_rows": sum(1 for r in rows if r.status == Status.OK),
        "coverage_pct": round(100 * len(ok) / len(eligible), 1) if eligible else 0.0,
        "status_counts": counts,
    }


def build_report(banks: list[Bank], rows: list[RateRow], summary: dict) -> str:
    by_bank: dict[str, list[RateRow]] = {}
    for r in rows:
        by_bank.setdefault(r.bank.name, []).append(r)

    lines = [
        f"# FD rates run - {summary['run_date']}",
        "",
        f"- Banks in seed list: **{summary['banks_total']}**",
        f"- Banks with a retail FD page to try: **{summary['banks_eligible']}**",
        f"- Banks with rates collected: **{summary['banks_ok']}** "
        f"({summary['coverage_pct']}% of eligible)",
        f"- Rate rows published: **{summary['rate_rows']}**",
        "",
        "## Coverage by category",
        "",
        "| Category | Collected | Eligible |",
        "| --- | ---: | ---: |",
    ]
    cats: dict[str, list[int]] = {}
    for b in banks:
        c = cats.setdefault(b.category, [0, 0])
        eligible = b.has_retail_fd and bool(b.rate_url)
        c[1] += int(eligible)
        if eligible and any(r.status == Status.OK for r in by_bank.get(b.name, [])):
            c[0] += 1
    for cat, (got, tot) in sorted(cats.items()):
        lines.append(f"| {cat} | {got} | {tot} |")

    manual = [
        (b, by_bank.get(b.name, []))
        for b in banks
        if not any(r.status == Status.OK for r in by_bank.get(b.name, []))
        and b.has_retail_fd
    ]
    lines += [
        "",
        "## Check these by hand",
        "",
        "Open each link in a normal browser and read the rate off the page. "
        "These are not failures of the data - they are banks whose sites refuse "
        "automated access or whose layout the parser does not recognise yet.",
        "",
        "| Bank | Status | Why | Link |",
        "| --- | --- | --- | --- |",
    ]
    for bank, rs in manual:
        r = rs[0] if rs else None
        status = r.status if r else "unknown"
        why = (r.notes if r else "").replace("|", "/")[:110]
        url = (r.source_url_override if r and r.source_url_override else bank.rate_url)
        link = f"[open]({url})" if url else "_no URL in seed list_"
        lines.append(f"| {bank.name} | `{status}` | {why} | {link} |")

    no_fd = [b for b in banks if not b.has_retail_fd]
    if no_fd:
        lines += ["", "## No retail FD product", "",
                  "Carried in the CSV with `status=no_retail_fd` so the bank list stays complete.", ""]
        lines += [f"- {b.name}" for b in no_fd]

    lines += [
        "",
        "---",
        "",
        "Every published rate points at a file under `evidence/` in the same run "
        "folder - the exact bytes the number was read from.",
        "",
    ]
    return "\n".join(lines)
