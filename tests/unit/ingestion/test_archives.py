import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import pytest

from music_discovery.ingestion.archives import Archive, ChecksumMismatchError, download, extract


def zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buffer.getvalue()


PAYLOAD = zip_bytes({"fma_metadata/tracks.csv": b"a,b\n1,2\n"})
ARCHIVE = Archive(
    name="fma_metadata.zip",
    url="https://example.test/fma_metadata.zip",
    sha1=hashlib.sha1(PAYLOAD).hexdigest(),
    extracts_to="fma_metadata",
)


def client(body: bytes, calls: list[int]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_download_verifies_and_is_idempotent(tmp_path: Path) -> None:
    calls: list[int] = []
    path = download(ARCHIVE, tmp_path, client(PAYLOAD, calls))
    assert path.read_bytes() == PAYLOAD
    download(ARCHIVE, tmp_path, client(PAYLOAD, calls))
    assert len(calls) == 1, "verified file is not downloaded again"


def test_checksum_mismatch_leaves_nothing(tmp_path: Path) -> None:
    with pytest.raises(ChecksumMismatchError):
        download(ARCHIVE, tmp_path, client(b"corrupted", []))
    assert list(tmp_path.iterdir()) == []


def test_extract_once(tmp_path: Path) -> None:
    zip_path = download(ARCHIVE, tmp_path, client(PAYLOAD, []))
    out = extract(ARCHIVE, zip_path, tmp_path)
    assert (out / "tracks.csv").read_text() == "a,b\n1,2\n"
    (out / "tracks.csv").write_text("edited")
    extract(ARCHIVE, zip_path, tmp_path)
    assert (out / "tracks.csv").read_text() == "edited", "second call does not re-extract"


def test_extract_rejects_path_traversal(tmp_path: Path) -> None:
    evil = tmp_path / "evil.zip"
    evil.write_bytes(zip_bytes({"../outside.txt": b"x"}))
    with pytest.raises(ValueError, match="unsafe path"):
        extract(ARCHIVE, evil, tmp_path / "target")
