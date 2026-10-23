"""Optional LLM phrasing of track descriptions (OpenRouter free models via `StructuredLLM`).

The model sees only the claim list (id + template sentence) - never the catalog, the query
history or any identifier - and must return at most two sentences, each citing the claim ids
it rests on. The output is accepted only if the claim validator passes it and it keeps the
caveat the template would have shown (an unverified constraint is never dropped). Anything
else returns a reason, and the description service keeps the template. Disabled by default.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from music_discovery.descriptions.claim_validator import (
    CitedSentence,
    Claim,
    DescriptionConfig,
    validate,
)
from music_discovery.domain.protocols import StructuredLLM
from music_discovery.domain.schemas import TrackEvidence

PROMPT_PATH = Path(__file__).parent / "prompts" / "descriptions.md"
TASK = "descriptions"


class DraftSentence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    claim_ids: list[str]


class PhrasingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sentences: list[DraftSentence]


@dataclass(frozen=True)
class PhrasingOutcome:
    text: str | None
    reason: str | None = None
    model_id: str | None = None


def _load_prompt(path: Path) -> tuple[str, str]:
    _, front, body = path.read_text().split("---\n", 2)
    meta = dict(line.split(":", 1) for line in front.strip().splitlines())
    return meta["prompt_version"].strip(), body.strip()


class LLMPhrasing:
    def __init__(self, llm: StructuredLLM, config: DescriptionConfig) -> None:
        self._llm = llm
        self._config = config
        self.prompt_version, self._system = _load_prompt(PROMPT_PATH)

    def phrase(
        self,
        claims: Sequence[Claim],
        evidence: TrackEvidence,
        *,
        required: Sequence[str] = (),
    ) -> PhrasingOutcome:
        """`required` are claim ids the text must cite (the caveat the template shows)."""
        user = json.dumps([{"id": c.id, "claim": c.text} for c in claims], ensure_ascii=False)
        result = self._llm.generate(task=TASK, system=self._system, user=user, schema=PhrasingDraft)
        if result.parsed is None:
            return PhrasingOutcome(None, f"llm_{result.error_code}", result.model_id)
        sentences = [
            CitedSentence(s.text.strip(), tuple(s.claim_ids)) for s in result.parsed.sentences
        ]
        if not sentences or not all(s.text for s in sentences):
            return PhrasingOutcome(None, "empty_output", result.model_id)
        check = validate(sentences, claims, evidence, self._config)
        if not check.ok:
            return PhrasingOutcome(None, "; ".join(check.violations), result.model_id)
        cited = {c for s in sentences for c in s.claim_ids}
        if missing := [c for c in required if c not in cited]:
            return PhrasingOutcome(None, f"dropped caveat {missing}", result.model_id)
        return PhrasingOutcome(" ".join(s.text for s in sentences), None, result.model_id)
