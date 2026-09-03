# indiafd

Weekly fixed deposit interest rates from 58 Indian banks, published as a CSV
where **every row carries the link a human can open to check it**.

Runs every Monday at 06:30 IST on GitHub Actions, commits the result back to
this repo, and writes a report listing the banks a person still has to check by
hand.

---

## Defaults - change these if they are wrong for you

| Assumption | Where to change it |
| --- | --- |
| "First day of the week" = **Monday 06:30 IST** | `cron: "0 1 * * 1"` in `.github/workflows/weekly.yml` (01:00 UTC). Sunday would be `0 1 * * 0`. |
| Output is **committed to `main`** - no Pages site, no releases | the "Commit results" step in the same workflow |
| **Retail domestic FD only** - no NRE/NRO, no bulk or institutional deposits, no RD | the seed list `data/seed/banks.csv` and the per-bank parsers |
| Rates **as published on the page**; a limited-period special is captured only if it sits in the same rate table | `src/fdrates/parse.py` |
| Repository | `shashankagrawal24/indiafd` |

---

## Quick start

```bash
git clone https://github.com/shashankagrawal24/indiafd && cd indiafd
pip install -e ".[dev]"
python -m fdrates run --limit 5 --verbose      # try five banks live
```

Other commands:

```bash
python -m fdrates run                                    # all 58 banks
python -m fdrates run --only hdfc_bank_ltd --dry-run     # one bank, write nothing
python -m fdrates run --offline-dir tests/fixtures       # no network at all
python -m fdrates list                                   # bank slugs
python -m fdrates validate data/latest/fd_rates.csv      # schema check
pytest -q                                                # 37 offline tests
```

`data/example/` holds a sample run so you can see the output shape before the
first real collection. Those numbers come from test fixtures and are invented.

---

## Deploying it

The repo is ready to run; it just needs to exist on GitHub.

```bash
cd indiafd
git init && git add -A && git commit -m "init: weekly Indian bank FD rate collector"
git remote add origin https://github.com/shashankagrawal24/indiafd.git
git push -u origin main
gh workflow run "Weekly FD rates"        # first run, don't wait until Monday
gh run watch
```

Then, once:

1. **Settings → Actions → General → Workflow permissions** → *Read and write*, so
   the job can commit the weekly CSV.
2. Open the run's job summary. It reproduces `run_report.md`: coverage, and the
   banks that need a manual check.

Scheduled workflows are disabled automatically after 60 days without repo
activity. The weekly commit keeps it alive on its own.

---

## Output

`data/latest/fd_rates.csv` is overwritten each week. `data/history/<date>/`
keeps the run, its report, and `evidence/` - the exact bytes each number was
read from.

One row per **bank x tenure x customer type**. Long format, because banks
publish wildly different tenure ladders and a wide table would be mostly holes.

| column | meaning |
| --- | --- |
| `run_date` | collection date, IST |
| `bank_name`, `category` | verbatim from the seed list |
| `tenure_label` | exactly as the bank prints it: `444 days`, `1 year to less than 2 years` |
| `tenure_days_min`, `tenure_days_max` | parsed range; `tenure_days_max` empty means "and above" |
| `deposit_band` | e.g. `Below Rs. 3 crore`; empty when the page states none |
| `customer_type` | `general` / `senior` / `super_senior` |
| `rate_pct` | percent per annum, 2 dp. **Empty means not found - never a guess, never 0** |
| `source_url` | the page or PDF actually fetched. Open it to verify the row |
| `source_type` | `html` / `js` / `pdf` / `none` |
| `fetched_at_ist` | ISO 8601 timestamp of the fetch |
| `status` | `ok`, `blocked`, `parse_failed`, `url_missing`, `no_retail_fd`, `stale_parser` |
| `evidence_file` | path to the committed snapshot behind this row |
| `notes` | why a non-ok row is non-ok |

All 58 banks appear in every run. A bank that yields nothing still gets one row
carrying its status and its link, so nothing disappears silently.

Tenure arithmetic uses 1 month = 30 days and 1 year = 365 days. The verbatim
label is always kept so the approximation can be checked.

---

## Expect partial coverage. That is the design.

GitHub Actions runs from datacenter IPs. Several banks - South Indian Bank,
Bank of India, Indian Bank, ESAF, CSB, Federal, DBS among them - sit behind
Cloudflare, Radware or a WAF and will refuse the runner even though the URL
opens fine in your browser. The seed list flags these in its `Notes` column.

When that happens the pipeline records `status=blocked` with the reason and puts
the bank in the manual-check table in `run_report.md`. It does **not** retry
harder, rotate proxies, spoof headers or touch CAPTCHAs, and it obeys
`robots.txt`. A blocked bank is a correct outcome, not a bug to engineer around.

The run fails only on a crash, a schema violation, or coverage below 50% of
eligible banks - the last is the signal that something broke, rather than that a
few banks blocked the runner.

---

## When a bank's layout defeats the generic parser

`status=parse_failed` means the page was fetched but no rate table was
recognised. Fix it with a per-bank override:

1. Look at the snapshot in `data/history/<date>/evidence/<slug>.html`.
2. Write `src/fdrates/banks/<slug>.py` with a `parse(html) -> list[ParsedRate]`.
3. Register it in `src/fdrates/banks/__init__.py`:
   `OVERRIDES["<slug>"] = <slug>.parse`
4. Copy the snapshot into `tests/fixtures/` and add a test asserting the numbers
   that page actually showed, so the fix is locked in.

Get slugs with `python -m fdrates list`.

---

## Layout

```
src/fdrates/
  models.py     Bank, RateRow, the CSV schema, seed loading
  fetch.py      polite HTTP, robots.txt, retries, block detection, evidence
  parse.py      tenure/rate parsing, generic HTML + PDF table extractors
  pipeline.py   per-bank isolation, status assignment, CSV + report writing
  cli.py        run / list / validate
  banks/        per-bank parser overrides, registered by slug
data/seed/banks.csv        the 58-bank source list
data/latest/, data/history/  output
tests/                     37 offline tests, fixtures per page shape
.github/workflows/         weekly schedule + CI
```

---

## Known limits

- Fixtures in `tests/fixtures/` are synthetic. Replace them with real snapshots
  from `data/history/*/evidence/` after the first live run.
- Tables using `rowspan`/`colspan` heavily may extract unevenly; that is what
  per-bank overrides are for.
- The two PDF banks re-upload their rate card on each revision, so the link is
  re-resolved from the hub page each run; if the hub is blocked, the seed path
  is used and may 404.
- Bank sites change without notice. The `evidence/` snapshot is the record of
  what was actually published on the day.

---

Rates are collected from public bank pages for reference. They can be stale or
misparsed - confirm on the bank's own page, linked in every row, before acting
on them. Not investment advice.

MIT licensed.
