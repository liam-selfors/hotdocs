# R-ASSEMBLE-009

**R-ASSEMBLE-009** — MUST also expose a narrower assembly entry point
  producing a `CriterionBundle` — one acceptance criterion's own text, its
  covered requirement's text, the target component's `interface/` content,
  the glossary, `dependency_interfaces` (`D100`, below), and `testing`,
  the component's test spec as `specs/architecture/test-reuse.md` builds
  it (`D341`) — for `test-author`'s use. A `CriterionBundle` MUST NOT include the target
  component's `gen/<component>/` content, any other file under
  `requirements/`, or `constraints.md` — narrower than the `SpecBundle`
  R-ASSEMBLE-001–008 describe, not a variant of it, because
  `test-author`'s independence requirement (its own R-AUTHOR-002) depends
  on it seeing *less* than `generator` sees, not the same bundle with
  something added.

  **`dependency_interfaces` is the one deliberate exception to "less,
  never more"** (`D100`): for each id in the target component's own
  `depends_on`, its full `interface/` content, exactly the same content
  and the same `R-ASSEMBLE-002` rule `SpecBundle.dependency_interfaces`
  already follows. This is a third party's already-public,
  already-documented contract, never the target's own implementation —
  it does not let a test author see anything about the component under
  test it couldn't already see, only lets a fake it writes for a
  *dependency* match that dependency's real, documented signature and
  return shape instead of guessing. Found only once three real
  `generated-test` authorings for a component with real dependencies
  guessed wrong about a dependency's call shape in three different ways
  (`D100`), despite every one of those shapes being fully documented
  and already available to `generator` via this exact mechanism.

  **`testing` is the second exception**, and test-only: it says how a
  test builds fixtures, never what the component does, and `SpecBundle`
  never includes it (`D341`).
