# R-GEN-001

**R-GEN-001** — Given a `SpecBundle` in `cold` mode, the model call MUST
  be constructed from exactly the bundle's `spec` / `interface` /
  `constraints` / `dependency_interfaces` / `vars` / `glossary` fields —
  never `hint_code` (which is `null` in cold mode anyway, per
  `spec-bundle-assembler` R-ASSEMBLE-008) and never the component's current
  `gen/<component>/` content from any other source.
