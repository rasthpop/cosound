"""Deterministic feedback -> spec update rules for Agent C (base §8).

Each rule is a pure function `(spec, event, context) -> RuleResult`: a new spec (or the same
one when nothing changes) and a short change note for "what changed". The table:

| Event               | Change                                                     | Next   |
|---------------------|------------------------------------------------------------|--------|
| MORE_LIKE_THIS      | track -> reference_track_ids                               | refine |
| LESS_LIKE_THIS      | track -> negative_reference_track_ids                      | refine |
| NOT_RELEVANT        | track -> excluded_track_ids                                | refine |
| WRONG_INSTRUMENT    | exclude the track; note lower trust in semantic-only       | refine |
|                     | matches for the instrument; the preference stays           |        |
| MORE_OF_ATTRIBUTE   | raise the weight by delta, or add the preference; drop it  | refine |
|                     | from the negatives                                         |        |
| LESS_OF_ATTRIBUTE   | lower the weight by delta (below delta: removed and made   | refine |
|                     | negative), or add a soft negative preference               |        |
| SELECT_TRACK        | none                                                       | details|

Invariants: `original_query` never changes, hard constraints are never dropped (an attribute
change that would contradict one is rejected, not applied), and the track-set rules are
idempotent. An attribute is named either by a lexicon term ("electronic") or by a category
with the term as the value (`attribute="genre", value="vaporwave"`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from music_discovery.agents.lexicon_loader import CATEGORIES, Category, Lexicon, phrase
from music_discovery.agents.query_parser import PREFERENCE_FIELDS
from music_discovery.domain.enums import FeedbackType, NextAction
from music_discovery.domain.schemas import (
    ConstraintAttribute,
    ConstraintOperator,
    FeedbackEvent,
    SearchSpecification,
    WeightedPreference,
)
from music_discovery.retrieval.prompt_builder import with_prompts

DELTA = 0.2
NEXT_ACTION = {
    FeedbackType.SELECT_TRACK: NextAction.SHOW_DETAILS,
}


@dataclass(frozen=True)
class RuleResult:
    spec: SearchSpecification
    note: str | None
    """None when the spec did not change."""
    rejected: str | None = None
    """Why an attribute change was refused (it would contradict a hard constraint)."""


@dataclass(frozen=True)
class RuleContext:
    lexicon: Lexicon
    delta: float = DELTA


def next_action(event: FeedbackEvent) -> NextAction:
    return NEXT_ACTION.get(event.event_type, NextAction.REFINE_SEARCH)


def apply_rule(spec: SearchSpecification, event: FeedbackEvent, ctx: RuleContext) -> RuleResult:
    return RULES[event.event_type](spec, event, ctx)


# --- track rules ------------------------------------------------------------------------


def _update(spec: SearchSpecification, **changes: object) -> SearchSpecification:
    """A validated new version; prompts are rebuilt from the changed preferences."""
    data = spec.model_dump() | changes | {"spec_version": spec.spec_version + 1}
    return with_prompts(SearchSpecification.model_validate(data))


def _add(ids: Iterable[str], track_id: str) -> list[str]:
    return list(dict.fromkeys([*ids, track_id]))


def _remove(ids: Iterable[str], track_id: str) -> list[str]:
    return [t for t in ids if t != track_id]


def _track(event: FeedbackEvent) -> str:
    if event.track_id is None:
        raise ValueError(f"{event.event_type} needs a track_id")
    return event.track_id


def more_like_this(spec: SearchSpecification, event: FeedbackEvent, _: RuleContext) -> RuleResult:
    track = _track(event)
    if track in spec.reference_track_ids:
        return RuleResult(spec, None)
    new = _update(
        spec,
        reference_track_ids=_add(spec.reference_track_ids, track),
        negative_reference_track_ids=_remove(spec.negative_reference_track_ids, track),
        excluded_track_ids=_remove(spec.excluded_track_ids, track),
    )
    return RuleResult(new, f"more like {track}")


def less_like_this(spec: SearchSpecification, event: FeedbackEvent, _: RuleContext) -> RuleResult:
    track = _track(event)
    if track in spec.negative_reference_track_ids:
        return RuleResult(spec, None)
    new = _update(
        spec,
        negative_reference_track_ids=_add(spec.negative_reference_track_ids, track),
        reference_track_ids=_remove(spec.reference_track_ids, track),
    )
    return RuleResult(new, f"less like {track}")


def not_relevant(spec: SearchSpecification, event: FeedbackEvent, _: RuleContext) -> RuleResult:
    track = _track(event)
    if track in spec.excluded_track_ids:
        return RuleResult(spec, None)
    new = _update(
        spec,
        excluded_track_ids=_add(spec.excluded_track_ids, track),
        reference_track_ids=_remove(spec.reference_track_ids, track),
    )
    return RuleResult(new, f"removed {track}")


def wrong_instrument(
    spec: SearchSpecification, event: FeedbackEvent, ctx: RuleContext
) -> RuleResult:
    track = _track(event)
    instrument = event.value if isinstance(event.value, str) and event.value else None
    if instrument is None and event.attribute not in (None, "instrument"):
        instrument = event.attribute
    if instrument is not None:
        entry = ctx.lexicon.entries.get(phrase(instrument))
        instrument = entry.canonical if entry is not None else instrument
    named = instrument or "the requested instrument"
    trust = f"audio-only matches for {named} are trusted less in this session"
    excluded = not_relevant(spec, event, ctx)
    if excluded.note is None and trust in spec.uncertainties:
        return RuleResult(spec, None)
    uncertainties = list(dict.fromkeys([*excluded.spec.uncertainties, trust]))
    if excluded.note is None:
        new = _update(spec, uncertainties=uncertainties)
    else:  # already a new version: add the note without bumping it twice
        data = excluded.spec.model_dump() | {"uncertainties": uncertainties}
        new = SearchSpecification.model_validate(data)
    return RuleResult(new, f"removed {track} (wrong {named})")


# --- attribute rules --------------------------------------------------------------------


@dataclass(frozen=True)
class _Attribute:
    category: Category
    value: str


def resolve_attribute(attribute: str | None, value: object, lexicon: Lexicon) -> _Attribute | None:
    """`attribute` is a lexicon term, or a category name with the term in `value`."""
    attribute = (attribute or "").strip()
    value = value.strip() if isinstance(value, str) else None
    if attribute.casefold() in CATEGORIES and value:
        entry = lexicon.entries.get(phrase(value))
        category: Category = attribute.casefold()  # type: ignore[assignment]
        if entry is not None and entry.category == category:
            return _Attribute(category, entry.canonical)
        return _Attribute(category, value.casefold())
    if attribute.casefold() == "vocals":
        return _Attribute("vocals", "vocals")
    entry = lexicon.entries.get(phrase(attribute))
    return None if entry is None else _Attribute(entry.category, entry.canonical)


def _hard_conflict(spec: SearchSpecification, attr: _Attribute, more: bool) -> str | None:
    """A hard constraint that the change would contradict; feedback never drops one."""
    blocked = ConstraintOperator.EXCLUDED if more else ConstraintOperator.REQUIRED
    for c in spec.hard_constraints:
        if c.operator is not blocked:
            continue
        if attr.category == "vocals" and c.attribute is ConstraintAttribute.VOCALS:
            return f"vocals are {c.operator} by your request"
        if c.value is not None and c.value.casefold() == attr.value.casefold():
            return f"{attr.value} is {c.operator} by your request"
    return None


def _prefs(spec: SearchSpecification, category: Category) -> list[WeightedPreference]:
    return list(getattr(spec, PREFERENCE_FIELDS[category]))


def _attribute_rule(
    more: bool,
) -> Callable[[SearchSpecification, FeedbackEvent, RuleContext], RuleResult]:
    def rule(spec: SearchSpecification, event: FeedbackEvent, ctx: RuleContext) -> RuleResult:
        attr = resolve_attribute(event.attribute, event.value, ctx.lexicon)
        if attr is None:
            return RuleResult(spec, None, rejected=f"unknown attribute {event.attribute!r}")
        if attr.category == "vocals":
            # "more instrumental" means fewer vocals
            wants_vocals = more != (attr.value == "instrumental")
            vocals = _Attribute("vocals", "vocals")
            if conflict := _hard_conflict(spec, vocals, wants_vocals):
                return RuleResult(spec, None, rejected=conflict)
            return _vocals(spec, wants_vocals)
        if conflict := _hard_conflict(spec, attr, more):
            return RuleResult(spec, None, rejected=conflict)
        return (_more if more else _less)(spec, attr, ctx)

    return rule


def _vocals(spec: SearchSpecification, more: bool) -> RuleResult:
    current = spec.vocal_preferences
    if current in ("required", "excluded"):
        return RuleResult(spec, None)  # already a hard choice in the same direction
    target = "preferred" if more else "avoided"
    if current == target:
        return RuleResult(spec, None)
    return RuleResult(_update(spec, vocal_preferences=target), f"vocals {target}")


def _more(spec: SearchSpecification, attr: _Attribute, ctx: RuleContext) -> RuleResult:
    key = attr.value.casefold()
    prefs = _prefs(spec, attr.category)
    negatives = [p for p in spec.negative_preferences if p.value.casefold() != key]
    current = next((p for p in prefs if p.value.casefold() == key), None)
    if current is None:
        weight = ctx.lexicon.weights.get(attr.category, 0.7)
        prefs.append(WeightedPreference(value=attr.value, weight=weight, source_span=None))
        note = f"more {attr.value}"
    else:
        weight = min(1.0, current.weight + ctx.delta)
        if weight == current.weight and len(negatives) == len(spec.negative_preferences):
            return RuleResult(spec, None)
        prefs = [p.model_copy(update={"weight": weight}) if p is current else p for p in prefs]
        note = f"more {attr.value} ({current.weight:.2f} -> {weight:.2f})"
    changes = {PREFERENCE_FIELDS[attr.category]: prefs, "negative_preferences": negatives}
    return RuleResult(_update(spec, **changes), note)


def _less(spec: SearchSpecification, attr: _Attribute, ctx: RuleContext) -> RuleResult:
    key = attr.value.casefold()
    prefs = _prefs(spec, attr.category)
    negatives = list(spec.negative_preferences)
    current = next((p for p in prefs if p.value.casefold() == key), None)
    if current is not None and current.weight - ctx.delta >= ctx.delta:
        weight = round(current.weight - ctx.delta, 6)
        prefs = [p.model_copy(update={"weight": weight}) if p is current else p for p in prefs]
        note = f"less {attr.value} ({current.weight:.2f} -> {weight:.2f})"
    else:
        prefs = [p for p in prefs if p is not current]
        negative = next((p for p in negatives if p.value.casefold() == key), None)
        base = ctx.lexicon.cues.negative_weight
        if negative is None:
            negatives.append(WeightedPreference(value=attr.value, weight=base, source_span=None))
        else:
            raised = min(1.0, negative.weight + ctx.delta)
            if raised == negative.weight and current is None:
                return RuleResult(spec, None)
            negatives = [
                p.model_copy(update={"weight": raised}) if p is negative else p for p in negatives
            ]
        note = f"less {attr.value}"
    changes = {PREFERENCE_FIELDS[attr.category]: prefs, "negative_preferences": negatives}
    return RuleResult(_update(spec, **changes), note)


def select_track(spec: SearchSpecification, event: FeedbackEvent, _: RuleContext) -> RuleResult:
    return RuleResult(spec, None)


RULES: dict[
    FeedbackType, Callable[[SearchSpecification, FeedbackEvent, RuleContext], RuleResult]
] = {
    FeedbackType.MORE_LIKE_THIS: more_like_this,
    FeedbackType.LESS_LIKE_THIS: less_like_this,
    FeedbackType.NOT_RELEVANT: not_relevant,
    FeedbackType.WRONG_INSTRUMENT: wrong_instrument,
    FeedbackType.MORE_OF_ATTRIBUTE: _attribute_rule(more=True),
    FeedbackType.LESS_OF_ATTRIBUTE: _attribute_rule(more=False),
    FeedbackType.SELECT_TRACK: select_track,
}
