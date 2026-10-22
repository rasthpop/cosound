"""Evaluation inputs under data/evaluation/ and their validation (base.md §12).

Tracks are identified by their FMA track id in all evaluation files, so a person can match
rows to audio file names. `internal_track_id` maps them to catalog ids.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from music_discovery.domain.enums import DataSource, ExternalIdKind
from music_discovery.domain.ids import ExternalId, IdPrefix, stable_id
from music_discovery.domain.schemas import HardConstraint

MANIFEST_FILE = "fma_20_manifest.csv"
QUERIES_FILE = "queries.jsonl"
JUDGMENTS_FILE = "judgments.csv"
SPLIT_FILE = "split.json"
SPECS_FILE = "specs_manual.jsonl"

JUDGMENT_COLUMNS = (
    "query_id",
    "fma_track_id",
    "overall_relevance",
    "mood_relevance",
    "instrument_present",
    "constraint_satisfied",
    "judge",
    "basis",
    "judged_at",
)
ATTRIBUTE_CATEGORIES = ("mood", "instrument", "genre", "tempo", "energy", "texture", "era")


class DatasetError(ValueError):
    """Evaluation inputs are missing or inconsistent. Lists every problem found."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


def internal_track_id(fma_track_id: int) -> str:
    """Catalog id of an FMA track (same derivation as the FMA importer)."""
    return stable_id(
        IdPrefix.TRACK,
        ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value=str(fma_track_id)),
    )


class _Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class ManifestEntry(_Row):
    fma_track_id: int
    title: str
    artist: str
    genre: str
    audio_path: str
    license: str
    theme: str = ""
    listening_status: Literal["pending", "confirmed"] = "pending"

    @property
    def track_id(self) -> str:
        return internal_track_id(self.fma_track_id)


class ExpectedAttributes(_Row):
    mood: list[str] = []
    instrument: list[str] = []
    genre: list[str] = []
    tempo: list[str] = []
    energy: list[str] = []
    texture: list[str] = []
    era: list[str] = []
    vocals: Literal["required", "preferred", "avoided", "excluded", "unspecified"] = "unspecified"


class EvalQuery(_Row):
    query_id: str = Field(pattern=r"^q\d{2,}$")
    family: str
    text: str = Field(min_length=1)
    intent_notes: str = ""
    expected_attributes: ExpectedAttributes
    expected_hard_constraints: list[HardConstraint] = []
    has_relevant_in_corpus: bool | None = None


Relevance = Annotated[int, Field(ge=0, le=3)]


class Judgment(_Row):
    query_id: str
    fma_track_id: int
    overall_relevance: Relevance
    mood_relevance: Relevance | None = None
    instrument_present: Literal["yes", "no", "uncertain"] | None = None
    constraint_satisfied: Literal["yes", "no", "unknown"] | None = None
    judge: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    """What was heard. Never CLAP output."""
    judged_at: datetime

    @property
    def track_id(self) -> str:
        return internal_track_id(self.fma_track_id)


class Split(_Row):
    dev: list[str]
    test: list[str]
    seed: int
    method: str
    created_at: datetime

    def of(self, name: Literal["dev", "test", "all"]) -> list[str]:
        if name == "all":
            return [*self.dev, *self.test]
        return list(getattr(self, name))


@dataclass(frozen=True)
class EvalDataset:
    manifest: list[ManifestEntry]
    queries: list[EvalQuery]
    judgments: list[Judgment]
    split: Split | None
    specs: dict[str, dict[str, Any]]
    """Hand-written SearchSpecification payloads per query id (until Agent A, P06)."""

    def query(self, query_id: str) -> EvalQuery:
        return next(q for q in self.queries if q.query_id == query_id)

    def relevance(self, query_id: str) -> dict[int, int]:
        """FMA track id -> overall relevance, for one query."""
        return {
            j.fma_track_id: j.overall_relevance for j in self.judgments if j.query_id == query_id
        }

    def judgment(self, query_id: str, fma_track_id: int) -> Judgment | None:
        return next(
            (
                j
                for j in self.judgments
                if j.query_id == query_id and j.fma_track_id == fma_track_id
            ),
            None,
        )

    @property
    def corpus_ids(self) -> list[int]:
        return [m.fma_track_id for m in self.manifest]

    def judged_fraction(self) -> float:
        total = len(self.queries) * len(self.manifest)
        return len(self.judgments) / total if total else 0.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _blank_to_none(row: dict[str, str]) -> dict[str, str | None]:
    return {k: (v if v != "" else None) for k, v in row.items()}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_split(queries: Sequence[EvalQuery], *, seed: int, created_at: datetime) -> Split:
    """Deterministic 50/50 split by query *family*: a query and its rephrasings stay together."""
    families = sorted(
        {q.family for q in queries},
        key=lambda f: hashlib.sha256(f"{seed}:{f}".encode()).hexdigest(),
    )
    dev: list[str] = []
    test: list[str] = []
    target = len(queries) / 2
    for family in families:
        members = sorted(q.query_id for q in queries if q.family == family)
        (dev if len(dev) + len(members) <= target or len(test) >= target else test).extend(members)
    return Split(
        dev=sorted(dev),
        test=sorted(test),
        seed=seed,
        method="by_family_seeded_hash",
        created_at=created_at,
    )


def load_dataset(directory: Path, *, require_split: bool = True) -> EvalDataset:
    """Load and validate every evaluation input. Raises DatasetError listing all problems."""
    problems: list[str] = []

    def parse(model: type[_Row], rows: list[dict[str, Any]], label: str) -> list[Any]:
        parsed = []
        for i, row in enumerate(rows, start=1):
            try:
                parsed.append(model.model_validate(row))
            except ValidationError as exc:
                problems.append(f"{label} row {i}: {exc.errors(include_url=False)[0]['msg']}")
        return parsed

    manifest = parse(ManifestEntry, _read_csv(directory / MANIFEST_FILE), MANIFEST_FILE)
    queries = parse(EvalQuery, _read_jsonl(directory / QUERIES_FILE), QUERIES_FILE)
    judgments_path = directory / JUDGMENTS_FILE
    judgments = parse(
        Judgment,
        [_blank_to_none(r) for r in _read_csv(judgments_path)] if judgments_path.is_file() else [],
        JUDGMENTS_FILE,
    )
    specs_path = directory / SPECS_FILE
    specs = (
        {item["query_id"]: item["spec"] for item in _read_jsonl(specs_path)}
        if specs_path.is_file()
        else {}
    )
    split_path = directory / SPLIT_FILE
    split = (
        Split.model_validate_json(split_path.read_text(encoding="utf-8"))
        if split_path.is_file()
        else None
    )

    corpus = {m.fma_track_id for m in manifest}
    query_ids = [q.query_id for q in queries]
    if len(corpus) != len(manifest):
        problems.append("duplicate fma_track_id in manifest")
    if len(set(query_ids)) != len(query_ids):
        problems.append("duplicate query_id in queries")
    seen: set[tuple[str, int]] = set()
    for j in judgments:
        if j.query_id not in query_ids:
            problems.append(f"judgment for unknown query {j.query_id}")
        if j.fma_track_id not in corpus:
            problems.append(f"judgment for track {j.fma_track_id} outside the corpus")
        if (j.query_id, j.fma_track_id) in seen:
            problems.append(f"duplicate judgment {j.query_id}/{j.fma_track_id}")
        seen.add((j.query_id, j.fma_track_id))
    for query_id in specs:
        if query_id not in query_ids:
            problems.append(f"spec for unknown query {query_id}")
    if split is None:
        if require_split:
            problems.append(f"{SPLIT_FILE} is missing")
    else:
        in_split = split.dev + split.test
        if sorted(in_split) != sorted(query_ids) or len(set(in_split)) != len(in_split):
            problems.append("split must contain every query exactly once")
        families: dict[str, set[str]] = {}
        for q in queries:
            families.setdefault(q.family, set()).add("dev" if q.query_id in split.dev else "test")
        mixed = sorted(f for f, sides in families.items() if len(sides) > 1)
        if mixed:
            problems.append(f"query families split across dev and test: {mixed}")
    if problems:
        raise DatasetError(problems)
    return EvalDataset(
        manifest=manifest, queries=queries, judgments=judgments, split=split, specs=specs
    )
