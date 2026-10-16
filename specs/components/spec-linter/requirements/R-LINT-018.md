# R-LINT-018

**R-LINT-018** — The linter MUST resolve every `depends_on_guarantees`
  entry against the corpus and fail on any entry that does not resolve to
  an existing `G-<comp>-NNN` id, **and** separately fail when the resolved
  id's owning component is not already listed in this component's own
  `depends_on` (D16) — referencing a guarantee of a component you don't
  even depend on is meaningless, not just unresolved, so it gets its own
  distinct check rather than being folded into R-LINT-003's plain existence
  check.
