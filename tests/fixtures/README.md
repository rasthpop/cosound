# Test fixtures

Small, deterministic inputs for unit and integration tests.

## What may be stored here

- **Synthetic data** written for the test (preferred): minimal JSON/CSV with the real shape of Discogs responses or FMA `tracks.csv` headers.
- **Sanitized recordings** of external responses only when the source's terms allow storing them (see `docs/data-sources.md`, P02.T01). Strip tokens, user data and anything not needed by the test.
- **Generated audio**: tiny sine-wave or silent clips created by the test itself at runtime, not committed recordings.

## What must never be stored here

- Copyrighted audio, FMA audio files, or CLAP checkpoints.
- API tokens, cookies, or real user data.
- Large files (pre-commit rejects files over 500 KB).

## Layout

```
tests/fixtures/
├── discogs/    # release/master/artist/label payloads (P02.T03)
├── fma/        # tracks.csv / genres.csv with the two-row header (P02.T06)
└── ...
```
