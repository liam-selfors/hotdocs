# R-GATE-007

**R-GATE-007** — For a component marked `sealed: true`, MUST skip
  `spec-bundle-assembler` and `generator` entirely, and invoke
  `verifier-orchestrator` directly against the component's existing
  code at its declared `source_path` — proving its characterization
  tests (`acceptance/` criteria, §8) still pass against the unchanged,
  hand-maintained implementation. There is nothing to generate for a
  sealed component by definition; routing it through `generator` anyway
  would be both wasted cost and conceptually wrong, not merely
  inefficient.

  **Unconditional, never gated on a provenance check** — `R-GATE-001`
  never checks `provenance-checker` for a sealed component. A sealed
  component's `spec_bundle_hash` reflects only its *spec*, never
  `source_path`'s actual content, so a human editing the implementation
  directly would leave a prior `.provenance.json`'s hash unchanged;
  trusting that hit would mean never re-running the one check that
  could catch that edit silently breaking something.

  This is the primary enforcement layer behind the sealed-component
  write-protection invariant (`generator`'s `R-GEN-009` is the
  independent, secondary layer). If a sealed component's requirements
  changed in a way the existing hand-maintained code no longer
  satisfies, this surfaces as an ordinary characterization-test failure
  here, blocking the merge the normal way — the fix is a human editing
  `source_path` directly. `license-scanner`/`secret-scanner` still
  cache normally against this component's unchanged content
  (`R-GATE-005` applies regardless of `sealed` status) — only the
  characterization-test re-run is unconditional.
