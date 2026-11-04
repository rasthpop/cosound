# ADR-0007: LLM-first query parsing and result selection

- **Status:** Accepted (owner decisions recorded 2026-11-04; the wording is open for review on the P11 pull request)
- **Date:** 2026-11-04
- **Phase/Task:** P11.T01; supersedes ADR-0004 decision 1; affects P06, P08, P09, P10

## Context

ADR-0004 kept every LLM path off by default, because no free model could beat a deterministic
parser scoring 1.000 attribute F1 on the dev queries. That score has a known limit: the lexicon
was written against the same labels, so it shows consistency rather than generalization. The
lexicon has real gaps on other wording. On 2026-11-04, the feedback reader, which uses the same
lexicon, found no attributes in "more like a rainy night drive". The query parser has not been
measured on such wording yet; P11.T02 adds a query set that does.

The owner has decided the LLM should do the work on each search: parsing the query and choosing
what comes back from the dataset. Three constraints shape how:

- **The LLM can't read the dataset directly.** It can't hear audio, 8,000 tracks do not fit a
  free model's limits, and sending them would be a catalog dump.
- **Search has to keep working.** Target T10 (ADR-0006) is a must: search works with the LLM
  unavailable. Free models fail, rate-limit and disappear.
- **Nothing may be invented.** base §3 and targets T8 and T9 still apply.

## Decision

The LLM reads the query and plans the search, the hybrid engine runs that plan over the catalog
and returns a bounded shortlist, and the LLM chooses and orders tracks from the shortlist. That
is two LLM calls per search, with no tool loop (base §19 rules out autonomous loops).

1. **Parsing is LLM-first.** The parser runs only on fallback. The LLM may accept hard constraints
   the parser did not find, if the cue and value appear verbatim in the query.
2. **Selection is LLM-first.** It returns ordered aliases only, with no free text, and every alias
   must come from the shortlist. Engine scores stay as computed, as evidence.
3. **Hard constraints stay enforced in code.** The shortlist is built after constraint filtering.
4. **`retrieval/` stays LLM-free.** LLM calls live in `agents/`, and baselines are unaffected.
5. **Every fallback is labelled** in the API response, never presented as an LLM result.
6. **Agent C stays code-only** (`LLM_FEEDBACK=false`), and description phrasing stays off (ADR-0004,
   decision 3). Agent C's feedback reader has known bugs, to be fixed separately in code.

### Owner decisions (2026-11-04)

| Decision | Choice |
|---|---|
| Send a shortlist to the LLM | **Yes.** About 30 tracks per search; fields are title, artist, album, genres, tags and year |
| Daily quota | **50 requests per day**, free tier only, no credits bought |
| Data policy | **Owner confirms** having checked the chosen models' policies and blocked training providers in the OpenRouter account. Not independently verified. |
| `LLM_DATA_COLLECTION` | Stays `deny` |

Never sent: track IDs, URLs, licenses, raw scores, user or session identifiers, secrets, or
anything beyond the shortlist. A model not already listed in ADR-0004 goes back to the owner for a
data-policy check before it is used.

## Consequences

- **The fallback becomes a normal path.** The limit of 50 requests per day (OpenRouter docs, read
  2026-10-23; re-check in P11.T04) allows about 25 uncached searches, and failed attempts may use
  more. After that, searches run on the deterministic path until the quota resets. So the labelling
  must be clear, the cache matters, and the adapter must stop retrying once the daily limit is hit.
- **Evaluation is slow.** One model over the 8 judged dev queries, the 10 Agent A queries and the
  paraphrase set can exceed one day's quota, so P11.T04 and P11.T10 spread over several days and
  rely on the response cache. Few models can be compared.
- **Latency target T12 will not hold as drafted.** p95 ≤ 2 s cannot realistically include two LLM
  calls. T12 is still a draft, so the owner should re-set it before the P10.T01 freeze (P11.T11).
- **The evaluation changes.** T1–T4 currently name the hybrid system. The LLM system becomes
  primary, and each evaluation-driven change is a cycle in `docs/crisp-dm/iterations.md`.
- **Cycle C5 narrows.** C5 tunes the deterministic CLAP prompt expansions. Those now only run on
  fallback, and at this quota fallback is common, so C5 stays worthwhile.
- **Data leaves the machine on each search:** the query text and shortlisted track facts. FMA
  metadata is public, but queries are user text, so `deny` and the account block remain required.
- **Rank and score can disagree.** The LLM's order need not follow engine scores, so views and
  explanations must not imply that it does (P11.T07, P11.T09).
- base §6–7 describe Agent B as primarily deterministic. This ADR records the deviation; similarity
  is still computed by code, as base §7 requires.

## Reversible by

Setting `LLM_QUERY=false` and `LLM_SELECTION=false` (added in P11.T03), or leaving `LLM_PROVIDER`
empty. Both restore today's deterministic behaviour with no other change, because the deterministic
paths stay as fallbacks and `retrieval/` is untouched.
