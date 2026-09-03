# Fixtures

**These files are synthetic.** They are hand-written stand-ins that reproduce the
*shapes* of real Indian bank rate pages, not copies of them:

| file | shape being tested |
| --- | --- |
| `state_bank_of_india.html` | plain tenure / general / senior table |
| `punjab_national_bank.html` | `<th>` headers, "Period", ROI wording, deposit band in a heading |
| `hdfc_bank_ltd.html` | two tables, one per amount band, plus a navigation table that must be ignored |
| `icici_bank_ltd.html` | amount-band columns that headers do not label as "general" |
| `hsbc_ltd.html` | single rate column, no senior citizen rates |
| `standard_chartered_bank_ltd.html` | awkward tenure labels: ranges, "and above", "less than" |
| `jana_small_finance_bank_ltd.html` | super senior citizen column |
| `ujjivan_small_finance_bank_ltd.html` | no `<th>` at all - positional fallback |
| `south_indian_bank_ltd.html` | Cloudflare interstitial - must come out as `blocked` |

Rates in these files are invented. Nothing here should ever be published as data.

## Replacing them with real snapshots

Once the pipeline has run against the live sites, real snapshots land in
`data/history/<date>/evidence/`. Copy one in when you need a regression test for
a specific bank's layout:

    cp data/history/2026-09-07/evidence/hdfc_bank_ltd.html tests/fixtures/

Then assert against the numbers that page actually showed on that date.
