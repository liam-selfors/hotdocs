# R-TRACK-003

**R-TRACK-003** — Each tracking record MUST be written as its own file
  under `.hotdocs/tracking/`, named so that lexicographic filename
  ordering matches chronological order (e.g. an ISO-8601-prefixed
  filename) — this is what lets `read_json('.hotdocs/tracking/*.json')`
  produce a naturally time-ordered table with no separate index. This
  directory MUST be gitignored (`SPEC_GUIDELINES.md` §1) and MUST NOT be
  created under `specs/`, `gen/`, or `verification/` — it is local
  developer-process state, not a spec artifact, same distinction the
  original brainstorm already draws between the corpus and its build
  outputs, extended here to a third category (observability) neither of
  those two is.
