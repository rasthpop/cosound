"""Name normalization shared by the Discogs normalizer and the cross-source matcher."""

from __future__ import annotations

import re
import unicodedata

_DISAMBIGUATOR = re.compile(r"\s+\(\d+\)$")
_NON_WORD = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def strip_disambiguator(name: str) -> str:
    """Discogs appends " (2)", " (3)" … to tell same-named artists apart; drop it for display."""
    return _DISAMBIGUATOR.sub("", name.strip())


def matching_key(text: str) -> str:
    """Aggressive normal form for comparing names and titles across sources.

    Casefolds, removes accents and punctuation, drops a Discogs disambiguator and a leading
    "the", and collapses whitespace. Only for comparison, never for display.
    """
    text = strip_disambiguator(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = _NON_WORD.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return text.removeprefix("the ").strip()
