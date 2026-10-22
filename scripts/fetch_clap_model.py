"""Download the pinned CLAP checkpoint (ADR-0002) and verify its weights.

    uv run python scripts/fetch_clap_model.py

Writes to CLAP_CHECKPOINT (default data/models/larger_clap_music_and_speech, git-ignored).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

from music_discovery.infrastructure.settings import get_settings

REPO_ID = "laion/larger_clap_music_and_speech"
REVISION = "195c3a3e68faebb3e2088b9a79e79b43ddbda76b"
WEIGHTS = "pytorch_model.bin"
WEIGHTS_SHA256 = (
    "b73c5e596fda5b29b522a1ab3f0842977fe2b147bf8b78c2ec5f7ae6267038a1"  # pragma: allowlist secret
)
FILES = [
    "config.json",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
    WEIGHTS,
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    settings = get_settings()
    target = settings.clap_checkpoint or settings.data_dir / "models" / REPO_ID.split("/")[1]
    snapshot_download(repo_id=REPO_ID, revision=REVISION, local_dir=target, allow_patterns=FILES)
    actual = sha256_of(target / WEIGHTS)
    if actual != WEIGHTS_SHA256:
        print(f"checksum mismatch for {WEIGHTS}: {actual}", file=sys.stderr)
        return 1
    (target / "REVISION").write_text(f"{REPO_ID}@{REVISION}\n", encoding="utf-8")
    print(f"verified {REPO_ID}@{REVISION} in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
