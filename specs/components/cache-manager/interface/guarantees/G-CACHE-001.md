# G-CACHE-001

**G-CACHE-001** — Writes to the same cache key from concurrent callers
  MUST be safe under last-write-wins semantics, **given** that every
  concurrent writer produces the same result payload for that key by
  construction (the determinism D13 already requires of every gate). A
  caller MAY rely on this without its own locking or coordination.

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
