# R-ASSIST-005

**R-ASSIST-005** — MUST check whether a changed requirement restates
  behavior already specified elsewhere in the corpus. Candidates are
  found deterministically first. A requirement's text is its file's
  contents exactly as read; its words are found by removing every match
  of `R-[A-Z0-9]+(-[A-Z0-9]+)*-[0-9]+[a-z]?`, lowercasing, and keeping
  the runs of `[a-z0-9_]` three or more characters long. A pair is a
  candidate when a changed requirement and any unchanged requirement in
  `<repo_root>/specs/components/*/requirements/` have a word-set Jaccard
  similarity of at least `0.35`. Each changed requirement keeps its five
  highest-scoring candidates, ties broken by id. With a `model` and at
  least one candidate, one model call's prompt holds each candidate
  pair's two texts and asks which pairs describe the same behavior; with
  no candidate, no redundancy call is made and `redundancy_flags` is
  `[]`.

  Each `redundancy_flags` entry MUST be `{new_requirement, overlaps_with,
  rationale}`: `new_requirement` a changed requirement's id,
  `overlaps_with` the other requirement's id, and `rationale` required.
  An entry whose pair was not among the candidates is dropped.
