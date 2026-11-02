# Evidence & copy audit — Discover screen

U05.T03, 2026-11-02. The `evidence-auditor` agent reviewed every user-visible string in
`frontend/src/components/**` and `frontend/src/pages/**` (copy, labels, tooltips, aria-labels, state
messages, the map caption) and the mock fixtures, against `ux-states-and-evidence` and
`grounded-explanations`. Fixture descriptions and match reasons were also run through the claim
validator's sentence checks (`descriptions/claim_validator.py`).

**Result: no unresolved findings.** Nine findings were fixed. One (S3) needs an API field and is now
the contract tasks P08.T13 / P09.T13. Notes were fixed or are explained below.

## What passed as-is

- **No percentages, probabilities or raw scores.** There is no percentage formatter, and no view uses
  `score`, `score_breakdown` or neighbor scores. Bands come only from `match_strength` and `score_bands`.
- **No implied detection.** All track descriptions come from the API. Static copy talks about the query,
  not the track. The instrument picker offers only the instruments named in the query.
- **Honest map.** The caption says "Nearness is suggestive, not exact". Neighbors come from the API and
  are headed by metric ("Nearby in sound" / "Related in the catalog"), never by map distance.
- **Missing stays absent.** Formatters return `null` and views skip it. "Unknown" and "N/A" appear
  nowhere. A missing band reads "not available", never 0.
- **Text as returned.** Description and match reasons are rendered as the API sends them; an empty
  description renders nothing.
- **Degraded states and errors.** They are stated plainly; error copy is chosen by `error.code`, and
  server messages or ids are never shown.

## Findings and resolutions

| # | Finding | Resolution |
|---|---|---|
| S1 | Fixture descriptions didn't match the real templates. One failed the claim validator (curly quotes around a prompt containing "featuring"). "Tagged Folk." named no source. A semantic-down track was described as having no audio analysis. | `api/examples.py` now builds descriptions with the exact templates of `description_service.py`: `Its audio is a strong match for "chill music with a flute".`, `Listed under "Folk" in FMA.`, reason `Tagged: Folk`. Semantic down: `Audio search was unavailable; matched on catalog metadata.` + `Metadata only`. No audio: `Audio analysis unavailable; …` + `No audio analysis`. All fixture descriptions and reasons now pass the validator. |
| S2 | The example data contradicted itself. Tracks without audio (3, 5) were placed on the audio map. Track 2's genre differed between results and map. Result coordinates differed from map coordinates. A "same artist" related track named another artist. | One consistent example world: the map holds the audio tracks 1, 2, 4, 6, 7. Genre, artist, audio and coordinates agree across every fixture, and the related track is `same_label`. Fixtures regenerated; tests updated. |
| S3 | Row mini-players play audio with no license next to them; `TrackResult` has no license field. | Contract request: **P08.T13** adds `TrackResult.audio` (`AudioInfo`), and **P09.T13** carries it to the frontend, flagged for the UI so that `ResultRow` then shows the license and FMA credit beside the player. Not worked around in the UI. The drawer's player already shows both. |
| S4 | The drawer left out the evidence and uncertainty notes. For a track opened from the map, "no audio analysis" wasn't said at all. | The drawer renders `EvidenceNote`: the row's flags for a track opened from the plate, and `detail.evidence_status` for one opened from the map (`pages/DetailsLayer.tsx`). Tested. |
| S5 | "You're offline" / "Offline" also appeared when only the server was down. | "Can't reach the server" in both the state view and the status pill. |
| S6 | The neighbor fallback reason `semantic_unavailable` showed as the raw "Semantic unavailable". | Labelled: "Sound-based matching is unavailable, so these tracks are related through the catalog instead." |
| S7 | Evidence-status labels said "Matched on …", but `evidence_status` only says what evidence exists. | Relabelled: "Audio analysis and catalog data" / "No audio analysis for this track" / "Audio analysis only (no catalog data)". `metadata_only` and the `no_audio` flag share wording, so they show once. |
| S8 | The drawer mixed genres, styles and free-form tags in one unlabelled list: a "flute" tag read like a detected instrument. | Two labelled groups, "FMA genres" and "FMA tags". Row badges are labelled "FMA genres and styles". |
| S9 | The "Only tracks with audio" toggle did nothing (every map point comes from the audio projection) and implied the opposite. | Removed from the map container (the view still supports it if the backend ever serves points without audio). |
| N1 | The map's accessible name "Map of tracks by audio similarity" had no hedge. | "Map of tracks arranged by audio similarity (approximate)". |
| N2 | The position caption was shown in the WebGL fallback, where no positions are drawn. | Left out there. |
| N3 | Instrument feedback read like a system finding: "(wrong flute)", "Wrong instrument in …". | "(you marked flute as wrong)", "Mark a requested instrument as wrong for …". |
| N4 | "the language model didn't answer": a fallback can also come from invalid output. | "Read by the built-in parser instead of the language model." |
| N8 | The FMA credit didn't state the metadata license. | "Audio and metadata from the Free Music Archive (FMA); metadata CC BY 4.0." (`docs/data-sources.md`). |

## Notes kept as they are

- **Validator hits that aren't track claims.** The query uncertainty "vocals are both excluded and
  requested" and the no-match reason "no track has reliable evidence for: vocals excluded" name
  "vocals" outside quotes. They describe the user's query, not a track. The same goes for the example
  queries and the search placeholder.
- **`change_summary` strings with raw ids** ("excluded trk_example_1") are backend strings. The change
  strip uses the structured `changes` whenever they are present, which the API always sends with a
  refinement (P08.T12). The strings appear only as a fallback.
- **Mock placeholders** ("Example Track 1", "Example license") are only loaded in mock mode.
- **Backend reason strings** are shown as returned, in lowercase; they are honest. Response `warnings`
  are not rendered directly; the status pill and chips cover the same states.
