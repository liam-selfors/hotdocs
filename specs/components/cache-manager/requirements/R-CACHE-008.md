# R-CACHE-008

**R-CACHE-008** — This component MAY evict any entry at any time, for any
  reason, without coordinating with or notifying any caller. No caller
  MUST ever assume a prior `put` guarantees a later `get` for the same key
  will hit.

  An evicted entry is a plain miss; the exact policy (size bound, TTL,
  none) is unpinned.
