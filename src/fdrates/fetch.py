"""Fetch layer: polite, honest, and happy to give up.

Rules baked in here:
  * one honest User-Agent, no spoofing, no proxy rotation, no CAPTCHA work
  * robots.txt is checked and obeyed
  * max one request per host every REQUEST_GAP seconds
  * a bot wall is a normal result (Outcome.blocked), never an exception
"""

from __future__ import annotations

import time
import urllib.robotparser as robotparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

import httpx

from .parse import looks_blocked

USER_AGENT = (
    "india-fd-rates/0.1 (+https://github.com/OWNER/india-fd-rates; "
    "weekly public FD rate collection; contact via repo issues)"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"}
TIMEOUT = 20.0
RETRIES = 3
REQUEST_GAP = 3.0  # seconds between requests to the same host
BLOCKING_STATUS = {401, 403, 405, 406, 409, 429, 503}


@dataclass
class Outcome:
    ok: bool
    content: bytes = b""
    text: str = ""
    url: str = ""
    http_status: int | None = None
    blocked: bool = False
    note: str = ""
    elapsed_ms: int = 0

    @property
    def is_pdf(self) -> bool:
        return self.content[:5] == b"%PDF-"


def strip_tracking(url: str) -> str:
    parts = urlsplit(url)
    query = "&".join(
        p for p in parts.query.split("&")
        if p and not p.lower().startswith(("utm_", "gclid", "fbclid"))
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


class Fetcher:
    def __init__(self, respect_robots: bool = True, gap: float = REQUEST_GAP):
        self.client = httpx.Client(
            headers=HEADERS, timeout=TIMEOUT, follow_redirects=True, verify=True
        )
        self.respect_robots = respect_robots
        self.gap = gap
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}

    # ------------------------------------------------------------- politeness
    def _wait(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            delay = self.gap - (time.monotonic() - last)
            if delay > 0:
                time.sleep(delay)
        self._last_hit[host] = time.monotonic()

    def _robots_allows(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        host = urlparse(url).netloc
        if host not in self._robots:
            rp = robotparser.RobotFileParser()
            robots_url = f"{urlparse(url).scheme}://{host}/robots.txt"
            try:
                resp = self.client.get(robots_url, timeout=10.0)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None  # no robots served -> nothing to disallow
            except Exception:
                rp = None
            self._robots[host] = rp
        rp = self._robots[host]
        if rp is None:
            return True
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:
            return True

    # ------------------------------------------------------------------ fetch
    def get(self, url: str) -> Outcome:
        url = strip_tracking(url)
        if not url:
            return Outcome(ok=False, note="empty url")
        if not self._robots_allows(url):
            return Outcome(ok=False, url=url, blocked=True, note="robots.txt disallows this path")

        host = urlparse(url).netloc
        started = time.monotonic()
        last_note, last_status = "", None

        for attempt in range(1, RETRIES + 1):
            self._wait(host)
            try:
                resp = self.client.get(url)
            except Exception as exc:  # network/TLS/DNS
                last_note = f"{type(exc).__name__}: {str(exc)[:120]}"
                time.sleep(2 ** attempt)
                continue

            last_status = resp.status_code
            if resp.status_code in BLOCKING_STATUS:
                last_note = f"HTTP {resp.status_code}"
                if resp.status_code in (429, 503) and attempt < RETRIES:
                    time.sleep(2 ** attempt)
                    continue
                return Outcome(
                    ok=False, url=str(resp.url), http_status=resp.status_code,
                    blocked=True, note=f"HTTP {resp.status_code} (bot wall or WAF)",
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
            if resp.status_code >= 400:
                last_note = f"HTTP {resp.status_code}"
                time.sleep(2 ** attempt)
                continue

            content = resp.content
            text = "" if content[:5] == b"%PDF-" else resp.text
            marker = looks_blocked(text) if text else None
            if marker:
                return Outcome(
                    ok=False, content=content, text=text, url=str(resp.url),
                    http_status=resp.status_code, blocked=True,
                    note=f"challenge page detected ({marker})",
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
            return Outcome(
                ok=True, content=content, text=text, url=str(resp.url),
                http_status=resp.status_code,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )

        return Outcome(
            ok=False, url=url, http_status=last_status,
            note=last_note or "fetch failed after retries",
            blocked=last_status in BLOCKING_STATUS if last_status else False,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    # ------------------------------------------------- javascript-rendered pages
    def get_rendered(self, url: str) -> Outcome:
        """Headless render. Used only for banks marked 'HTML (JS)' in the seed."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return Outcome(ok=False, url=url, blocked=True,
                           note="playwright not installed; run: playwright install chromium")
        started = time.monotonic()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(args=["--disable-dev-shm-usage"])
                page = browser.new_page(user_agent=USER_AGENT, locale="en-IN")
                page.goto(strip_tracking(url), timeout=45000, wait_until="networkidle")
                try:
                    page.wait_for_selector("table", timeout=15000)
                except Exception:
                    pass
                html = page.content()
                browser.close()
        except Exception as exc:
            return Outcome(ok=False, url=url, note=f"render failed: {str(exc)[:140]}",
                           elapsed_ms=int((time.monotonic() - started) * 1000))
        marker = looks_blocked(html)
        if marker:
            return Outcome(ok=False, text=html, url=url, blocked=True,
                           note=f"challenge page detected ({marker})")
        return Outcome(ok=True, content=html.encode("utf-8"), text=html, url=url,
                       http_status=200, elapsed_ms=int((time.monotonic() - started) * 1000))

    # ------------------------------------------------------------ pdf handling
    def resolve_pdf_url(self, hub_url: str, seed_url: str) -> tuple[str, str]:
        """PDF rate cards get re-uploaded on every revision, so find the current
        link on the hub page first and only fall back to the seed path."""
        from bs4 import BeautifulSoup

        if not hub_url:
            return seed_url, "no hub page; used seed URL"
        out = self.get(hub_url)
        if not out.ok or not out.text:
            return seed_url, f"hub page unavailable ({out.note or 'no content'}); used seed URL"
        soup = BeautifulSoup(out.text, "lxml")
        keywords = ("interest", "rate", "deposit", "fd", "term")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" not in href.lower():
                continue
            haystack = f"{href} {a.get_text(' ')}".lower()
            if any(k in haystack for k in keywords):
                return urljoin(str(out.url or hub_url), href), "PDF link resolved from hub page"
        return seed_url, "no PDF link found on hub page; used seed URL"

    def close(self) -> None:
        self.client.close()


def save_evidence(directory: Path, slug: str, outcome: Outcome) -> str:
    """Write the exact bytes we parsed. Every published rate points at one of these."""
    directory.mkdir(parents=True, exist_ok=True)
    if outcome.is_pdf:
        ext = "pdf"
    elif outcome.text or outcome.content:
        ext = "html"
    else:
        ext = "txt"
    path = directory / f"{slug}.{ext}"
    payload = outcome.content or (outcome.text or outcome.note).encode("utf-8")
    path.write_bytes(payload)
    return str(path)
