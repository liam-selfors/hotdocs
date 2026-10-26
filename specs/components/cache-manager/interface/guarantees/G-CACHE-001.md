# G-CACHE-001

**G-CACHE-001** — Writes to the same cache key from concurrent callers
  MUST be safe under last-write-wins semantics: no write MUST corrupt,
  partially overwrite, or merge with another. For a deterministic gate
  (`license-scanner`, `secret-scanner`, any `compiled`-kind gate — D13's
  default), every concurrent writer produces an identical payload for a
  given key by construction, so it never matters which write survives.
  For a gate whose own `constraints.md` scopes determinism more
  narrowly (`generator`, `test-author` — only a cache *hit* is required
  to be byte-identical, not every call capable of producing one), two
  concurrent misses on the same key MAY legitimately produce two
  different, independently-valid payloads; last-write-wins then means
  whichever survives is still a correct, uncorrupted answer for that
  key — an arbitrary but valid choice between two acceptable results,
  not a sign anything broke. A caller MAY rely on `get`/`put`'s
  atomicity without its own locking or coordination; no caller MAY rely
  on a `put` it issued being the one a later `get` for the same key
  returns.

  **What a dependent is actually promised here, concretely:** a `get`
  issued shortly after a concurrent `put` for the same key, from a
  *different* caller than the one that wrote it, MAY safely be treated as
  authoritative the moment it returns a hit — no staleness window, no
  eventual-consistency delay, as long as the precondition above holds.
  This is the worked example D16 was built around: if `cache-manager`'s
  backing store ever changes from a single-node store to one with weaker
  consistency (e.g. a distributed cluster with eventual consistency across
  nodes), *that* is a change to this guarantee, not an internal detail —
  it lives here, under `interface/`, specifically so such a change is
  visible to and propagates toward whatever depends on it (D16), rather
  than silently invalidating an assumption nobody could see was being
  relied upon.
