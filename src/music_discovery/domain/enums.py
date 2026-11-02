"""Enumerations shared across the domain. Tri-state facts never use booleans."""

from enum import StrEnum


class DataSource(StrEnum):
    DISCOGS = "discogs"
    FMA = "fma"
    ECHONEST = "echonest"
    CLAP = "clap"
    HUMAN = "human"
    DERIVED = "derived"


class ExternalIdKind(StrEnum):
    RELEASE = "release"
    MASTER = "master"
    ARTIST = "artist"
    LABEL = "label"
    TRACK = "track"


class Evidence(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class ConstraintStatus(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class EvidenceStatus(StrEnum):
    AUDIO_AND_METADATA = "audio_and_metadata"
    METADATA_ONLY = "metadata_only"
    AUDIO_ONLY = "audio_only"


class FeedbackType(StrEnum):
    """Feedback event types from base.md §8 (wire values are UPPER_SNAKE)."""

    MORE_LIKE_THIS = "MORE_LIKE_THIS"
    LESS_LIKE_THIS = "LESS_LIKE_THIS"
    NOT_RELEVANT = "NOT_RELEVANT"
    WRONG_INSTRUMENT = "WRONG_INSTRUMENT"
    MORE_OF_ATTRIBUTE = "MORE_OF_ATTRIBUTE"
    LESS_OF_ATTRIBUTE = "LESS_OF_ATTRIBUTE"
    SELECT_TRACK = "SELECT_TRACK"


class NextAction(StrEnum):
    REFINE_SEARCH = "REFINE_SEARCH"
    SHOW_DETAILS = "SHOW_DETAILS"
    NONE = "NONE"


class SearchOutcomeKind(StrEnum):
    OK = "ok"
    NO_CONFIDENT_MATCH = "no_confident_match"
    NEEDS_CLARIFICATION = "needs_clarification"


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class InterpreterStatus(StrEnum):
    USED = "used"
    FALLBACK = "fallback"
    DISABLED = "disabled"


class RetrievalSource(StrEnum):
    METADATA = "metadata"
    SEMANTIC = "semantic"
    RELATIONSHIP = "relationship"


class RelationshipType(StrEnum):
    SAME_ARTIST = "same_artist"
    SAME_LABEL = "same_label"
    SAME_MASTER = "same_master"
    SAME_RELEASE = "same_release"
    SHARED_STYLE = "shared_style"


class MatchStatus(StrEnum):
    ACCEPTED = "accepted"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"


class MatchStrength(StrEnum):
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"
