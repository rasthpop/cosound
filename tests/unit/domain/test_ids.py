import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from music_discovery.domain.enums import DataSource, ExternalIdKind
from music_discovery.domain.ids import (
    ID_NAMESPACE,
    ExternalId,
    IdPrefix,
    id_prefix,
    is_valid_id,
    random_id,
    stable_id,
)

values = st.text(min_size=1, max_size=20).filter(lambda s: s.strip() == s and s != "")


def test_same_source_key_gives_same_id() -> None:
    ext = ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value="2")
    again = ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value="2")
    assert stable_id(IdPrefix.TRACK, ext) == stable_id(IdPrefix.TRACK, again)
    assert stable_id(IdPrefix.TRACK, ext).startswith("trk_")


def test_known_value_is_stable_across_runs() -> None:
    ext = ExternalId(source=DataSource.DISCOGS, kind=ExternalIdKind.RELEASE, value="249504")
    expected = uuid.uuid5(ID_NAMESPACE, "discogs:release:249504").hex
    assert stable_id(IdPrefix.RELEASE, ext) == f"rel_{expected}"


@given(value=values)
def test_different_sources_never_collide(value: str) -> None:
    fma = ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value=value)
    discogs = ExternalId(source=DataSource.DISCOGS, kind=ExternalIdKind.TRACK, value=value)
    assert stable_id(IdPrefix.TRACK, fma) != stable_id(IdPrefix.TRACK, discogs)


@given(a=values, b=values)
def test_different_values_never_collide(a: str, b: str) -> None:
    if a == b:
        return
    ea = ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value=a)
    eb = ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value=b)
    assert stable_id(IdPrefix.TRACK, ea) != stable_id(IdPrefix.TRACK, eb)


def test_kinds_do_not_collide() -> None:
    release = ExternalId(source=DataSource.DISCOGS, kind=ExternalIdKind.RELEASE, value="1")
    master = ExternalId(source=DataSource.DISCOGS, kind=ExternalIdKind.MASTER, value="1")
    assert stable_id(IdPrefix.RELEASE, release)[4:] != stable_id(IdPrefix.RELEASE, master)[4:]


def test_external_id_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value="  ")


def test_external_id_is_frozen() -> None:
    ext = ExternalId(source=DataSource.FMA, kind=ExternalIdKind.TRACK, value="2")
    with pytest.raises(ValidationError):
        ext.value = "3"  # type: ignore[misc]


def test_prefix_helpers() -> None:
    session = random_id(IdPrefix.SESSION)
    assert is_valid_id(session, IdPrefix.SESSION)
    assert not is_valid_id(session, IdPrefix.TRACK)
    assert random_id(IdPrefix.SESSION) != session
    assert id_prefix("xyz_123") is None
    assert id_prefix("not-an-id") is None
