# Data understanding report

Generated 2026-11-02 10:45 UTC by `scripts/data_understanding.py` (CRISP-DM step 2, `docs/adr/0006-crisp-dm.md`). Read-only; regenerate rather than edit.

## Catalog

- Tracks: **8000** (fma: 8000)
- Validated, decodable audio: 7993 (99.9 %)
- Audio embeddings: 7993 (99.9 %); only these tracks are on the map and in sound-based search
- Tracks without audio: 7 (trk_04a0975c8d2f5be594d754fc97d9db05, trk_30de824fcd6a50e8a9881571e21bc557, trk_3252aeaef5715d6aa4796a3b0a108df6, trk_973444bda5945188a91cb43250b4884e, trk_98f2d5d0b54a5da98b40f6d830b8d80b, trk_a996adc24cfc53439e2161cb36f647fa, trk_d12ea26150515f44af84a28218477317)

### Field completeness

Missing values are counted, never filled (missing is not zero).

| Field | Present | Share |
|---|---|---|
| `artists` | 8000 | 100.0 % |
| `year` | 5337 | 66.7 % |
| `genres` | 8000 | 100.0 % |
| `styles` | 0 | 0.0 % |
| `tags` | 1361 | 17.0 % |
| `duration_seconds` | 8000 | 100.0 % |
| `release_id` | 8000 | 100.0 % |
| `source_url` | 8000 | 100.0 % |
| `audio_path` | 7993 | 99.9 % |
| `audio_embedding_id` | 7993 | 99.9 % |

### Genre balance (first genre per track, the map colour)

| Genre | Tracks | Share |
|---|---|---|
| Folk | 1000 | 12.5 % |
| Hip-Hop | 1000 | 12.5 % |
| Electronic | 1000 | 12.5 % |
| Instrumental | 1000 | 12.5 % |
| Rock | 1000 | 12.5 % |
| Experimental | 1000 | 12.5 % |
| Pop | 1000 | 12.5 % |
| International | 1000 | 12.5 % |

Genre tags per track: 1: 2137, 2: 3657, 3: 1749, 4: 402, 5: 49, 6: 6

### Audio licenses

- Attribution-Noncommercial-Share Alike 3.0 United States: 1232
- Attribution-NonCommercial-NoDerivatives (aka Music Sharing) 3.0 International: 998
- Creative Commons Attribution-NonCommercial-NoDerivatives 4.0: 967
- Attribution-NonCommercial-ShareAlike 3.0 International: 912
- Attribution-Noncommercial-No Derivative Works 3.0 United States: 694
- Attribution-NonCommercial-ShareAlike: 607
- Attribution: 547
- Attribution-NonCommercial: 473
- Attribution-NonCommercial 3.0 International: 399
- Creative Commons Attribution: 221
- … 53 more license texts (943 tracks); full list in profile.json

## Evaluation inputs

- Corpus: 20 tracks; listening status pending: 20
- Queries: 20 in 16 families; dev 10 test 10
- Judged pairs: 220 of 400 (55.0 %)
- Fully judged queries: 11 (q01, q02, q03, q04, q05, q06, q10, q11, q12, q16, q18)
- Documented minimum (`judging_minimum.json`): dev q01, q03, q06, q10, q11, q12, q16, q18; test q02, q04, q05
- Required but not fully judged: none

### Relevance

Overall relevance distribution (0-3, all judged pairs): 0: 121, 1: 45, 2: 34, 3: 20

| Query | Judged | Relevant (≥ threshold) |
|---|---|---|
| q01 | 20 | 3 |
| q02 | 20 | 6 |
| q03 | 20 | 4 |
| q04 | 20 | 3 |
| q05 | 20 | 7 |
| q06 | 20 | 6 |
| q07 | 0 | — |
| q08 | 0 | — |
| q09 | 0 | — |
| q10 | 20 | 4 |
| q11 | 20 | 5 |
| q12 | 20 | 6 |
| q13 | 0 | — |
| q14 | 0 | — |
| q15 | 0 | — |
| q16 | 20 | 1 |
| q17 | 0 | — |
| q18 | 20 | 9 |
| q19 | 0 | — |
| q20 | 0 | — |

Fully judged queries without any relevant track: none

### Hard constraints

Queries with hard constraints: q06, q12, q16, q17. Their constraint judgments: no: 22, unknown: 20, yes: 18

### Judgments to review

These rows look inconsistent with the judge's own listening note (heuristic; a person decides, nothing is changed automatically):

| Query | FMA track | constraint_satisfied | Note | Problem |
|---|---|---|---|---|
| q06 | 35184 | yes | vocals present | marked as satisfying 'no vocals', but the note says vocals are heard |
| q06 | 45152 | yes | vocals present, song is not calm | marked as satisfying 'no vocals', but the note says vocals are heard |
| q06 | 107476 | no | vocals are not present, not calm | marked as violating 'no vocals', but the note says there are none |
