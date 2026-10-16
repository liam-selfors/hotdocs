# R-CACHE-003

**R-CACHE-003** — `put` MUST be safe to call concurrently (from parallel
  gate runs, per D13's "parallelize independent gates") without corrupting
  either entry. Conflict policy: last-write-wins per key is acceptable *only*
  if the two writers would have produced the same result for the same key by
  construction (D13's determinism requirement on every gate) — `put` MUST NOT
  silently merge or partially overwrite a stored result.
