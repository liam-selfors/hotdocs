# R-CACHE-008

**R-CACHE-008** — This component MAY evict any entry at any time, for any
  reason, without coordinating with or notifying any caller. No caller
  MUST ever assume a prior `put` guarantees a later `get` for the same key
  will hit.

  **Resolves the eviction/retention open question by establishing that it
  has no correctness dimension to resolve:** `R-CACHE-001` already
  requires `get` to return a definitive miss, never an approximation, and
  `R-CACHE-004` already requires a backing-store problem to degrade to
  "nothing is cached yet," never a crash. An evicted entry is, from a
  caller's perspective, indistinguishable from either of those — a plain
  miss, already a fully specified, correct outcome everywhere a cache
  lookup happens in this corpus. Eviction only ever affects **hit rate**
  (and therefore cost, per D13), never correctness. The exact
  policy — a size bound, a TTL, both, neither — is deliberately left
  unpinned here: the backing store is pluggable (`VAR-CACHE-STORE-URL`),
  and the right policy genuinely depends on which store it ends up being
  (a size bound makes sense for a local file-based store; a TTL makes more
  sense for a managed, shared one) — a single number pinned in this spec
  would be guessing at operational conditions this component has no
  visibility into.
