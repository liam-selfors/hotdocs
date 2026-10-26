# Bootstrap Account: `spec-bundle-assembler`

Sixth hand-authored bootstrap exception — temporary, like `cache-manager`:
nothing stops a real `generator` from cold-regenerating this component
later.

**Reuses `spec-linter`'s own `load_corpus()`** rather than re-parsing
spec files independently (`SPEC_GUIDELINES.md` §10, single source of
truth) — `assemble()`/`assemble_criterion()` both work directly against
the already-parsed `Component`/`Doc` structures `spec_linter.py` exposes.
`R-ASSEMBLE-010`'s dependency-`Purpose` field is read via
`graph-query-engine`'s `component_context` view specifically, never
directly from a dependency's `component.md` by this component's own
logic — confirmed by a real test (`AC-ASSEMBLE-010`) that a dependency's
`Rationale` section content (`D13`, in the fixture) never reaches the
assembled bundle, only its dependent-safe `Purpose` text does.

**`depends_on` was missing `comp-graph-query-engine`** — the same drift
`D44`/`D45` already found and fixed twice elsewhere — fixed here too
(`D49`).

Verified against a synthetic fixture (a `comp-foo`/`comp-bar` pair with a
real dependency edge, a var, and a product capability) — needed for
precise control over scenarios the real corpus can't currently exercise
cleanly: a dependency with known `Purpose`/`Rationale` text to assert the
exclusion boundary on, and a deliberately-broken corpus to exercise
`R-ASSEMBLE-005`'s precondition-failure path without actually breaking
this repo's own real corpus. All 10 tests pass (one per `AC-ASSEMBLE-*`
criterion).

Also smoke-tested against this repo's own real corpus directly
(`assemble("comp-cache-manager", ...)` and `assemble("comp-spec-linter",
...)`), confirming `dependency_interfaces`/`dependency_context` populate
correctly for a component with a real dependency, and that no
`acceptance/` content leaks in even though `spec-linter`'s own
`requirements/` text happens to discuss the `Covers:`/`Kind:` tag
convention by name (a legitimate requirement discussing the convention,
not a leaked criterion file — checked by hand, not assumed).
