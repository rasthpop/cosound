"""In-memory field-weighted BM25 index (implements `domain.protocols.LexicalIndex`).

Each document is a mapping of field name to text. A term may span several tokens
("drum and bass"); it matches a field only when all of its tokens occur in that field.
The catalog is small (thousands of tracks), so the index is rebuilt in memory at startup.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Casefold, strip accents, split on anything that is not a letter or digit."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return _TOKEN.findall(text.replace("&", " and "))


@dataclass(frozen=True)
class BM25Params:
    k1: float = 1.2
    b: float = 0.75


class BM25FieldIndex:
    def __init__(
        self,
        documents: Mapping[str, Mapping[str, str]],
        *,
        field_weights: Mapping[str, float],
        params: BM25Params | None = None,
    ) -> None:
        self._weights = dict(field_weights)
        self._params = params or BM25Params()
        self._tf: dict[str, dict[str, Counter[str]]] = {}
        self._length: dict[str, dict[str, int]] = {}
        doc_freq: dict[str, Counter[str]] = defaultdict(Counter)
        total_length: Counter[str] = Counter()
        for doc_id, fields in documents.items():
            self._tf[doc_id] = {}
            self._length[doc_id] = {}
            for field, text in fields.items():
                if field not in self._weights:
                    continue
                tokens = tokenize(text)
                counts = Counter(tokens)
                self._tf[doc_id][field] = counts
                self._length[doc_id][field] = len(tokens)
                total_length[field] += len(tokens)
                doc_freq[field].update(set(counts))
        n = max(len(documents), 1)
        self._n = n
        self._avg_length = {f: total_length[f] / n for f in self._weights}
        self._idf = {
            f: {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq[f].items()}
            for f in self._weights
        }

    @property
    def size(self) -> int:
        return len(self._tf)

    def _field_score(self, doc_id: str, field: str, tokens: Sequence[str]) -> float:
        counts = self._tf[doc_id].get(field)
        if not counts or any(t not in counts for t in tokens):
            return 0.0
        k1, b = self._params.k1, self._params.b
        length = self._length[doc_id][field]
        avg = self._avg_length.get(field) or 1.0
        score = 0.0
        for token in tokens:
            tf = counts[token]
            idf = self._idf[field].get(token, 0.0)
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg))
        return score

    def score(self, doc_id: str, terms: Sequence[str]) -> float:
        if doc_id not in self._tf:
            return 0.0
        total = 0.0
        for term in terms:
            tokens = tokenize(term)
            if not tokens:
                continue
            total += sum(w * self._field_score(doc_id, f, tokens) for f, w in self._weights.items())
        return total

    def search(
        self, terms: Sequence[str], k: int, *, restrict_to: Collection[str] | None = None
    ) -> list[tuple[str, float]]:
        if k <= 0:
            return []
        pool = self._tf.keys() if restrict_to is None else [d for d in restrict_to if d in self._tf]
        scored = [(d, s) for d in pool if (s := self.score(d, terms)) > 0.0]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:k]

    def matches(self, doc_id: str, terms: Sequence[str]) -> list[tuple[str, str]]:
        fields = self._tf.get(doc_id, {})
        found: list[tuple[str, str]] = []
        for term in terms:
            tokens = tokenize(term)
            if not tokens:
                continue
            for field, counts in fields.items():
                if all(t in counts for t in tokens):
                    found.append((field, term))
        return found
