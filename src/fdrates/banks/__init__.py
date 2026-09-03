"""Per-bank parser overrides.

The generic table extractor in fdrates/parse.py handles most banks. When it
gets one wrong, add a module here and register it. Nothing else changes.

    # src/fdrates/banks/example_bank.py
    from ..parse import ParsedRate

    def parse(html: str) -> list[ParsedRate]:
        ...

    # then, below:
    from . import example_bank
    OVERRIDES["example_bank_ltd"] = example_bank.parse

The key is the bank slug: lowercase Bank Name from the seed CSV with every
non-alphanumeric run replaced by an underscore, e.g.
"HDFC Bank Ltd" -> "hdfc_bank_ltd". Print them with:

    python -m fdrates list
"""

from __future__ import annotations

from collections.abc import Callable

# slug -> callable(html_or_text) -> list[ParsedRate]
OVERRIDES: dict[str, Callable] = {}


def get_override(slug: str) -> Callable | None:
    return OVERRIDES.get(slug)
