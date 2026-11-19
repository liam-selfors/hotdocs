# R-GEN-019

**R-GEN-019** — The prompt MUST always
  instruct the candidate that any value read from a dependency call —
  including the dependency function's own top-level return value, not
  only values nested within it — MUST use dual dict-or-attribute
  access, never a bare `.attr` access alone: a dependency may return
  either a dict or an object (`D139`).
