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
`Rationale` section content (`D21`, in the fixture) never reaches the
assembled bundle, only its dependent-safe `Purpose` text does.

**`depends_on` was missing `comp-graph-query-engine`** — the same drift
already found and fixed twice elsewhere (in `spec-linter` and
`corpus-graph-builder`'s own bootstraps) — fixed here too.

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

**`dependency_usage` (`R-ASSEMBLE-011`, `D37`)** — the direct fix for
generator's own self-regeneration import failure. Introspects a dependency's real `gen/` code via
`inspect` (never source text, never a model call); respects `__all__`
when a package defines one (`corpus-graph-builder`'s own convention),
falls back to a `__module__`-filtered scan of top-level
functions/classes otherwise (every flat-module component so far).
Confirmed directly against the real corpus: `assemble("comp-generator",
...)` now surfaces `cache_manager.CacheKey`'s real constructor
signature by name — exactly the fact `generator`'s own self-regeneration
attempt was missing when it guessed wrong about `cache-manager`'s
module layout.

**`D60`: sealed dependencies were silently invisible.** Only ever
checked `gen/<dependency>/` — `criterion-compiler` (`sealed: true`,
real code at `pipeline/criterion-compiler/`) always degraded to an
empty usage card, indistinguishable from "no real code yet." Found
only once a real dependent (`capability-scenario-verifier`) actually
needed real usage info for it. Fixed by checking the dependency's own
`component.md` for a `sealed: true` + `source_path` pair first, via a
new `_dependency_real_code_dir` helper, before falling back to the
normal `gen/<dependency>/` location — confirmed directly: `_dependency_
usage(Path("."), "criterion-compiler")` now surfaces `compile`,
`compile_criterion`, and every other real public symbol by name and
signature.
