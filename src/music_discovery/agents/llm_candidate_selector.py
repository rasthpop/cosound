"""LLM choice and order of results from the engine's shortlist (Agent B, ADR-0007).

The hybrid engine has already enforced hard constraints and dropped duplicates, so anything chosen
from the shortlist is allowed. The model sees each candidate under an opaque alias, with only the
fields the owner approved: title, artist, album, genres, tags and year. Track IDs, URLs, licenses,
scores and user or session identifiers are never sent.

The model answers with ordered aliases and no free text, so nothing it writes can reach a user as
a claim about a track. Catalog text is untrusted input: the worst a malicious title can do is
influence the order among shortlisted tracks, because any alias outside the shortlist rejects the
whole answer. A rejected answer returns a reason, and the caller keeps the engine's order.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from music_discovery.agents.llm_query_interpreter import Prompt, load_prompt
from music_discovery.domain.protocols import StructuredLLM
from music_discovery.domain.schemas import SearchSpecification

PROMPT_PATH = Path(__file__).parent / "prompts" / "selection.md"
TASK = "selection"
MAX_TEXT_CHARS = 200


class SelectionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected: list[str]


@dataclass(frozen=True)
class ShortlistTrack:
    """One engine candidate. `track_id` stays on this side and is never sent to the model."""

    track_id: str
    title: str
    artists: Sequence[str] = ()
    album: str | None = None
    genres: Sequence[str] = ()
    tags: Sequence[str] = ()
    year: int | None = None


@dataclass(frozen=True)
class SelectionOutcome:
    track_ids: list[str] | None
    """Chosen tracks, best first; None means keep the engine's order."""
    fallback_reason: str | None = None
    model_id: str | None = None


class LLMCandidateSelector:
    def __init__(
        self,
        llm: StructuredLLM,
        *,
        shortlist_size: int,
        max_tags: int,
        prompt: Prompt | None = None,
    ) -> None:
        self._llm = llm
        self._shortlist_size = shortlist_size
        self._max_tags = max_tags
        self._prompt = prompt or load_prompt(PROMPT_PATH)

    @property
    def prompt_version(self) -> str:
        return self._prompt.version

    @property
    def shortlist_size(self) -> int:
        return self._shortlist_size

    def select(
        self,
        spec: SearchSpecification,
        shortlist: Sequence[ShortlistTrack],
        *,
        limit: int,
        timeout_s: float | None = None,
    ) -> SelectionOutcome:
        if limit > self._shortlist_size:
            return SelectionOutcome(None, "limit_exceeds_shortlist")
        if len(shortlist) > self._shortlist_size:  # the guard against sending a catalog dump
            return SelectionOutcome(None, "shortlist_too_large")
        if not shortlist:
            return SelectionOutcome(None, "empty_shortlist")

        by_alias = {f"c{i}": track for i, track in enumerate(shortlist, start=1)}
        result = self._llm.generate(
            task=TASK,
            system=self._prompt.text,
            user=self._user_message(spec, by_alias, limit),
            schema=SelectionDraft,
            timeout_s=timeout_s,
        )
        if result.parsed is None:
            return SelectionOutcome(None, f"llm_{result.error_code}", result.model_id)
        aliases = result.parsed.selected
        if not aliases:
            return SelectionOutcome(None, "llm_found_nothing", result.model_id)
        if any(alias not in by_alias for alias in aliases):
            return SelectionOutcome(None, "unknown_alias", result.model_id)
        if len(set(aliases)) != len(aliases):
            return SelectionOutcome(None, "duplicate_alias", result.model_id)
        chosen = [by_alias[alias].track_id for alias in aliases[:limit]]
        return SelectionOutcome(chosen, None, result.model_id)

    def _user_message(
        self, spec: SearchSpecification, by_alias: dict[str, ShortlistTrack], limit: int
    ) -> str:
        wanted = [p.value for prefs in spec.positive_preferences.values() for p in prefs]
        return json.dumps(
            {
                "request": spec.original_query,
                "wanted": wanted,
                "avoid": [p.value for p in spec.negative_preferences],
                "vocals": spec.vocal_preferences,
                "limit": limit,
                "candidates": [self._candidate(a, t) for a, t in by_alias.items()],
            },
            ensure_ascii=False,
        )

    def _candidate(self, alias: str, track: ShortlistTrack) -> dict[str, object]:
        return {
            "alias": alias,
            "title": _clip(track.title),
            "artists": [_clip(a) for a in track.artists],
            "album": None if track.album is None else _clip(track.album),
            "genres": [_clip(g) for g in track.genres],
            "tags": [_clip(t) for t in track.tags[: self._max_tags]],
            "year": track.year,
        }


def _clip(text: str) -> str:
    return text[:MAX_TEXT_CHARS]
