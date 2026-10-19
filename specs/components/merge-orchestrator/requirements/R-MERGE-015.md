# R-MERGE-015

**R-MERGE-015** — For a cache miss (same precondition as R-MERGE-004) on a
  component marked `sealed: true`, MUST skip `spec-bundle-assembler`,
  `generator`, the best-of-k retry loop, and `cross-model-divergence-
  checker` entirely, and invoke `verifier-orchestrator` directly against
  the component's existing code at its declared `source_path` — proving
  its characterization tests (`acceptance/` criteria, §9) still pass
  against the unchanged, hand-maintained implementation. There is nothing
  to generate for a sealed component by definition; routing it through
  `generator` anyway would be both wasted cost and conceptually wrong, not
  merely inefficient.

  This is the primary enforcement layer behind the sealed-component
  write-protection invariant (`generator`'s R-GEN-009 is the independent,
  secondary layer — in case this routing is ever bypassed) — previously
  only asserted in `generator`'s own `constraints.md` as something this
  component "should" do, never actually specified as its own requirement
  until now.

  If a sealed component's requirements changed in a way the existing
  hand-maintained code no longer satisfies, this surfaces as an ordinary
  characterization-test failure here, blocking the merge the normal way —
  the fix is a human editing `source_path` directly, not anything this
  component does differently.
