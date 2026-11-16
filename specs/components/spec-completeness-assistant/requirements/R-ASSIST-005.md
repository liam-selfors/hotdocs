# R-ASSIST-005

**R-ASSIST-005** — MUST check whether a changed requirement restates
  behavior already specified elsewhere in the corpus. Candidates are
  found deterministically first: a requirement's words are its text's
  lowercased runs of `[a-z0-9_]`, three or more characters long, with
  every requirement id removed; a pair is a candidate when a changed
  requirement and any requirement in `<repo_root>/specs/components/*/requirements/`
  that is not itself changed have a word-set Jaccard similarity of at
  least `0.35`. Each changed requirement keeps its five highest-scoring
  candidates, ties broken by id. With a `model` and at least one
  candidate, one model call's prompt holds each candidate pair's two
  full texts and asks which pairs describe the same behavior; with no
  candidate, no redundancy call is made and `redundancy_flags` is `[]`.

  Each `redundancy_flags` entry MUST be `{new_requirement, overlaps_with,
  rationale}`: `new_requirement` a changed requirement's id,
  `overlaps_with` the other requirement's id, and `rationale` required,
  since an entry exists only because a judgment flagged it. An entry
  whose pair was not among the candidates is dropped.
