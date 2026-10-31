# R-GEN-019

**R-GEN-019** — Regardless of `depends_on`, the prompt MUST always
  instruct the candidate that any value read from a dependency call —
  including the dependency function's own top-level return value, not
  only values nested within it — MUST use dual dict-or-attribute
  access, never a bare `.attr` access alone: a dependency may return
  either a dict or an object. Cross-cutting scaffolding like
  `R-GEN-018`.

  Found (`D139`) after a candidate applied dual access correctly to
  fields nested inside a dependency's returned entries, but not to
  the dependency's own top-level return value — the same partial
  pattern `R-TRACK-012` (`D121`) already found once elsewhere.
