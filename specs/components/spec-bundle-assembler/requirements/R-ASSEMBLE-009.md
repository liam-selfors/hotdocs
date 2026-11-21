# R-ASSEMBLE-009

**R-ASSEMBLE-009** — MUST also expose a narrower assembly entry point
  producing a `CriterionBundle` — one acceptance criterion's own text, its
  covered requirement's text, the target component's `interface/` content,
  the glossary, `dependency_interfaces` (`D100`, below), and `testing`,
  the component's test spec as `specs/architecture/test-reuse.md` builds
  it (`D341`), with `R-ASSEMBLE-016`'s asset-kind guidance — for
  `test-author`'s use. A `CriterionBundle` MUST NOT include the target
  component's `gen/<component>/` content, any other file under
  `requirements/`, or `constraints.md`: `test-author`'s independence
  (R-AUTHOR-002) depends on it seeing *less* than `generator` sees.

  **`dependency_interfaces` is the one deliberate exception to "less,
  never more"** (`D100`): for each id in the target component's own
  `depends_on`, its full `interface/` content, exactly the same content
  and the same `R-ASSEMBLE-002` rule `SpecBundle.dependency_interfaces`
  already follows. It is a dependency's public contract, never the
  target's implementation, and lets a test's fake for a dependency match
  its documented call shape instead of guessing.

  **`testing` is the second exception**, and test-only: it says how a
  test builds fixtures, never what the component does, and `SpecBundle`
  never includes it (`D341`).
