"""Download, verify and unpack dataset archives (FMA). Idempotent and checksum-verified."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx

CHUNK = 1 << 20


@dataclass(frozen=True)
class Archive:
    name: str
    url: str
    sha1: str
    extracts_to: str
    """Top-level directory the archive unpacks into."""


# Published SHA-1 checksums from https://github.com/mdeff/fma (not secrets).
FMA_ARCHIVES = {
    "metadata": Archive(
        name="fma_metadata.zip",
        url="https://os.unil.cloud.switch.ch/fma/fma_metadata.zip",
        sha1="f0df49ffe5f2a6008d7dc83c6915b31835dfe733",  # pragma: allowlist secret
        extracts_to="fma_metadata",
    ),
    "small": Archive(
        name="fma_small.zip",
        url="https://os.unil.cloud.switch.ch/fma/fma_small.zip",
        sha1="ade154f733639d52e35e32f5593efe5be76c6d70",  # pragma: allowlist secret
        extracts_to="fma_small",
    ),
}


class ChecksumMismatchError(RuntimeError):
    pass


def sha1_of(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download(archive: Archive, target_dir: Path, http: httpx.Client) -> Path:
    """Download to `<name>.part`, verify, then rename. Skips when a verified copy exists."""
    target_dir.mkdir(parents=True, exist_ok=True)
    final = target_dir / archive.name
    if final.is_file() and sha1_of(final) == archive.sha1:
        return final
    part = final.with_name(final.name + ".part")
    with http.stream("GET", archive.url, follow_redirects=True) as response:
        response.raise_for_status()
        with part.open("wb") as handle:
            for chunk in response.iter_bytes(CHUNK):
                handle.write(chunk)
    actual = sha1_of(part)
    if actual != archive.sha1:
        part.unlink()
        raise ChecksumMismatchError(f"{archive.name}: expected sha1 {archive.sha1}, got {actual}")
    part.replace(final)
    return final


def extract(archive: Archive, zip_path: Path, target_dir: Path) -> Path:
    """Unpack once. Refuses members that would escape `target_dir`."""
    out = target_dir / archive.extracts_to
    marker = out / ".extracted"
    if marker.is_file():
        return out
    root = target_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if not (root / member).resolve().is_relative_to(root):
                raise ValueError(f"unsafe path in archive: {member}")
        zf.extractall(target_dir)
    marker.write_text(archive.sha1, encoding="utf-8")
    return out
