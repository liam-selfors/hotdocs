# R-GEN-001

**R-GEN-001** — Given a `SpecBundle` in `cold` mode, the model call MUST
  be constructed from exactly the bundle's `spec`, `interface`,
  `constraints`, `dependency_interfaces`, `dependency_context`, `vars`
  and `glossary` fields and the non-empty entries of `dependency_usage`,
  in the sections `specs/architecture/generator-prompt.md` gives
  (`D325`) — never `hint_code` (`null` in cold mode, R-ASSEMBLE-008) and
  never the component's current `gen/<component>/` content from any
  other source.

  `retry_feedback` (`R-GEN-012`), a bare `R-id` list, is allowed.
