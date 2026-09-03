"""Command line entry point: python -m fdrates run"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .models import COLUMNS, load_banks
from .pipeline import run as run_pipeline

DEFAULT_SEED = Path("data/seed/banks.csv")
DEFAULT_OUT = Path("data")
MIN_COVERAGE = 50.0  # below this the run is treated as broken, not merely blocked


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fdrates", description="Weekly Indian bank FD rate collector")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="collect rates and write the CSV")
    r.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    r.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output root (default: data/)")
    r.add_argument("--limit", type=int, default=0, help="only the first N banks")
    r.add_argument("--only", action="append", default=[],
                   help="bank slug; repeatable. See: python -m fdrates list")
    r.add_argument("--offline-dir", type=Path, default=None,
                   help="parse snapshots from this directory instead of the live sites")
    r.add_argument("--dry-run", action="store_true", help="collect and report, write nothing")
    r.add_argument("--ignore-robots", action="store_true",
                   help="not recommended; robots.txt is obeyed by default")
    r.add_argument("--no-coverage-gate", action="store_true",
                   help="exit 0 even if coverage is below the minimum")
    r.add_argument("-v", "--verbose", action="store_true")

    lst = sub.add_parser("list", help="print bank slugs from the seed list")
    lst.add_argument("--seed", type=Path, default=DEFAULT_SEED)

    val = sub.add_parser("validate", help="check a published CSV against the schema")
    val.add_argument("csv_path", type=Path)
    return p


def cmd_run(args) -> int:
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s", stream=sys.stderr,
    )
    banks = load_banks(args.seed)
    if args.only:
        wanted = {s.lower() for s in args.only}
        banks = [b for b in banks if b.slug in wanted]
    if args.limit:
        banks = banks[: args.limit]
    if not banks:
        print("no banks selected", file=sys.stderr)
        return 2

    summary = run_pipeline(
        banks,
        out_root=args.out,
        offline_dir=args.offline_dir,
        dry_run=args.dry_run,
        respect_robots=not args.ignore_robots,
    )

    print(
        f"{summary['run_date']}: {summary['banks_ok']}/{summary['banks_eligible']} banks "
        f"collected ({summary['coverage_pct']}%), {summary['rate_rows']} rate rows"
    )
    for status, n in sorted(summary["status_counts"].items()):
        print(f"  {status:<14} {n}")

    if args.offline_dir or args.dry_run or args.no_coverage_gate:
        return 0
    if summary["coverage_pct"] < MIN_COVERAGE:
        print(f"coverage below {MIN_COVERAGE}% - treating as a broken run", file=sys.stderr)
        return 1
    return 0


def cmd_list(args) -> int:
    for b in load_banks(args.seed):
        print(f"{b.slug:<44} {b.category:<22} {b.page_format}")
    return 0


def cmd_validate(args) -> int:
    import csv

    from .models import RATE_MAX, RATE_MIN, CustomerType, Status

    with open(args.csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            print("column mismatch", file=sys.stderr)
            print(f"  expected: {COLUMNS}", file=sys.stderr)
            print(f"  found:    {reader.fieldnames}", file=sys.stderr)
            return 1
        problems = 0
        for i, row in enumerate(reader, start=2):
            if row["status"] not in Status.ALL:
                print(f"line {i}: bad status {row['status']!r}", file=sys.stderr)
                problems += 1
            if row["customer_type"] not in CustomerType.ALL:
                print(f"line {i}: bad customer_type {row['customer_type']!r}", file=sys.stderr)
                problems += 1
            if row["status"] == Status.OK:
                if not row["rate_pct"]:
                    print(f"line {i}: status ok with no rate", file=sys.stderr)
                    problems += 1
                elif not (RATE_MIN <= float(row["rate_pct"]) <= RATE_MAX):
                    print(f"line {i}: rate out of range {row['rate_pct']}", file=sys.stderr)
                    problems += 1
                if not row["source_url"]:
                    print(f"line {i}: status ok with no source_url", file=sys.stderr)
                    problems += 1
    print("schema ok" if not problems else f"{problems} problem(s)")
    return 0 if not problems else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return {"run": cmd_run, "list": cmd_list, "validate": cmd_validate}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
