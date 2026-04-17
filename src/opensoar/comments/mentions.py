"""Parse ``@username`` mention tokens out of comment text.

Usernames may contain lowercase ASCII letters, digits, underscores, dots, and
hyphens.  A mention must be preceded by a non-word character (or the start of
the string) so that email addresses like ``alice@example.com`` do not match.
Results are returned lowercased, deduplicated, and in the order they first
appear so downstream callers can line them up with a username lookup without
further processing.
"""
from __future__ import annotations

import re

# Word-boundary guard: the token must not be glued to the tail of another word
# (defeats ``alice@example.com``).  We rely on ``(?<![\w.])`` rather than ``\b``
# because ``\b`` treats ``.`` as a boundary and we want to keep dotted usernames.
_MENTION_RE = re.compile(r"(?<![\w@.])@([A-Za-z0-9_][A-Za-z0-9_.\-]{0,63})")


def parse_mention_tokens(text: str | None) -> list[str]:
    """Extract unique, order-preserving lowercase usernames from ``text``."""
    if not text:
        return []

    seen: set[str] = set()
    ordered: list[str] = []
    for match in _MENTION_RE.finditer(text):
        raw = match.group(1).rstrip(".-_")
        if not raw:
            continue
        token = raw.lower()
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered
