# FD rates run - 2026-09-21

- Banks in seed list: **58**
- Banks with a retail FD page to try: **49**
- Banks with rates collected: **22** (44.9% of eligible)
- Rate rows published: **2044**

## Coverage by category

| Category | Collected | Eligible |
| --- | ---: | ---: |
| Foreign Bank | 3 | 6 |
| Private Sector Bank | 11 | 21 |
| Public Sector Bank | 5 | 12 |
| Small Finance Bank | 3 | 10 |

## Check these by hand

Open each link in a normal browser and read the rate off the page. These are not failures of the data - they are banks whose sites refuse automated access or whose layout the parser does not recognise yet.

| Bank | Status | Why | Link |
| --- | --- | --- | --- |
| Bank of Baroda | `parse_failed` | page fetched but no rate table recognised - check the snapshot and add a per-bank parser | [open](https://bankofbaroda.bank.in/interest-rate-and-service-charges/deposits-interest-rates) |
| Bank of India | `blocked` | HTTP 403 (bot wall or WAF) | [open](https://bankofindia.bank.in/interest-rate-on-deposit) |
| Canara Bank | `parse_failed` | page fetched but no rate table recognised - check the snapshot and add a per-bank parser | [open](https://www.canarabank.bank.in/pages/deposit-interest-rates) |
| Indian Bank | `parse_failed` | HTTP 404 | [open](https://indianbank.bank.in/en/interest-rates-for-domestic-term-deposits) |
| Punjab and Sind Bank | `blocked` | challenge page detected (cloudflare) | [open](https://www.punjabandsind.bank.in/content/interestdom) |
| Punjab National Bank | `blocked` | challenge page detected (cloudflare) | [open](https://pnb.bank.in/Interest-Rates-Deposit.html) |
| UCO Bank | `blocked` | challenge page detected (cloudflare) | [open](https://www.uco.bank.in/en/web/guest/interest-rates-on-deposit-schemes) |
| CSB Bank Ltd | `blocked` | challenge page detected (captcha) | [open](https://www.csb.bank.in/interest-rates) |
| ICICI Bank Ltd | `blocked` | robots.txt disallows this path | [open](https://www.icici.bank.in/personal-banking/deposits/fixed-deposit/fd-interest-rates) |
| IDBI Bank Ltd | `parse_failed` | ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certifica | [open](https://www.idbi.bank.in/interest-rates.aspx) |
| Jammu and Kashmir Bank Ltd | `parse_failed` | ConnectTimeout: timed out | [open](https://jkb.bank.in/interest-rates) |
| Karur Vysya Bank Ltd | `parse_failed` | page fetched but no rate table recognised - check the snapshot and add a per-bank parser | [open](https://www.kvb.bank.in/interest-rates-charges-quick-glance/) |
| Kotak Mahindra Bank Ltd | `blocked` | challenge page detected (cloudflare) | [open](https://www.kotak.bank.in/en/rates/interest-rates.html) |
| Nainital Bank Ltd | `blocked` | challenge page detected (cloudflare) | [open](https://www.nainitalbank.bank.in/english/interest_rate.aspx) |
| RBL Bank Ltd | `blocked` | challenge page detected (cloudflare) | [open](https://www.rbl.bank.in/interest-rates?tab=fixed-deposit) |
| South Indian Bank Ltd | `blocked` | HTTP 403 (bot wall or WAF) | [open](https://www.southindianbank.bank.in/quick-links/interest-rates) |
| YES Bank Ltd | `parse_failed` | render failed: Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at https://www.yes.bank.in/rates-and-charges
Call log: | [open](https://www.yes.bank.in/rates-and-charges) |
| Bank of Bahrain & Kuwait B.S.C. | `parse_failed` | page fetched but no rate table recognised - check the snapshot and add a per-bank parser | [open](https://bbkindia.bank.in/wp-content/uploads/2025/05/CardRate-.pdf) |
| DBS India Bank Ltd | `blocked` | robots.txt disallows this path | [open](https://www.dbs.bank.in/in/treasures/deposits/fixed-deposit-interest-rate.page) |
| Doha Bank Q.P.S.C. | `url_missing` | No .bank.in domain registered and dohabank.co.in did not resolve during this check. Confirm current India site | _no URL in seed list_ |
| KEB Hana Bank | `url_missing` | Single branch India operation. No .bank.in domain and no India retail site resolving | _no URL in seed list_ |
| Kookmin Bank | `url_missing` | Single branch India operation, corporate focused. No India retail rate page found | _no URL in seed list_ |
| SBM Bank India Ltd | `blocked` | challenge page detected (cloudflare) | [open](https://www.sbm.bank.in/personal-banking/deposits/fixed-deposit/fixed-deposit-interest-rates) |
| Woori Bank | `url_missing` | Domain live but no public FD rate page located. Likely corporate focused India branches | _no URL in seed list_ |
| AU Small Finance Bank Ltd | `blocked` | hub page unavailable (robots.txt disallows this path); used seed URL; robots.txt disallows this path | [open](https://www.au.bank.in/notice-board/notice-board-folder-4/Interest-Rate-for-Domestic-NRE-NRO-Retail-FD-Rates.pdf) |
| Capital Small Finance Bank Ltd | `blocked` | challenge page detected (cloudflare) | [open](https://www.capital.bank.in/interest-rates/callable-domestic-term-deposit) |
| Equitas Small Finance Bank Ltd | `blocked` | HTTP 503 (bot wall or WAF) | [open](https://equitas.bank.in/personal-banking/save/fixed-deposits/) |
| ESAF Small Finance Bank Ltd | `blocked` | HTTP 403 (bot wall or WAF) | [open](https://www.esaf.bank.in/interest-rate/) |
| Shivalik Small Finance Bank Ltd | `url_missing` | Domain resolves but returned 503 throughout this check. Confirm the rate page path when the site is up | _no URL in seed list_ |
| Suryoday Small Finance Bank Ltd | `parse_failed` | ConnectError: [SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled (_ssl.c:1016) | [open](https://suryoday.bank.in/rate-of-interest/) |
| Unity Small Finance Bank Ltd | `parse_failed` | page fetched but no rate table recognised - check the snapshot and add a per-bank parser | [open](https://unity.bank.in/personal-banking/deposits/fixed-deposit) |
| Utkarsh Small Finance Bank Ltd | `parse_failed` | page fetched but no rate table recognised - check the snapshot and add a per-bank parser | [open](https://www.utkarsh.bank.in/personal/term-deposits/fixed-deposits) |

## No retail FD product

Carried in the CSV with `status=no_retail_fd` so the bank list stays complete.

- American Express Banking Corporation
- Bank of America
- Barclays Bank PLC
- Citi Bank

---

Every published rate points at a file under `evidence/` in the same run folder - the exact bytes the number was read from.
