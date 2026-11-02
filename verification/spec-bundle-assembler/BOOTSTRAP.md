# Bootstrap Account: `spec-bundle-assembler`

Sixth hand-authored bootstrap exception — temporary, like `cache-manager`.
The sections below cover the original hand-authored implementation.
**It has since been cold-generated for real (`D109`)** — see "Cold
generation (`D100`–`D109`)" at the end of this file for that arc.

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

## Cold generation (`D100`–`D109`)

`D100` added `dependency_interfaces` to this component's own
`CriterionBundle` — additive, but per `D36` a spec-driven component
can no longer be hand-edited for it, closing the "temporary exception"
README.md always said could end this way. `D101` fixed a `PyYAML`
misstep (the first real candidate reinvented frontmatter parsing
instead of reusing `spec-linter`'s own `load_corpus()`).

The much larger share of the real work was in `test-author`, not here
— `D102`–`D108` (full account in `verification/test-author/
BOOTSTRAP.md`), seven rounds fixing how `test-author` authors synthetic
test fixtures and calls the real model, none specific to this
component; they surfaced here only because this was the first
component with both real dependencies and a corpus-wide
lint-cleanliness precondition to have `generated-test` criteria
authored against it for real:

- `D102`: fixtures missing required frontmatter (`title`/`owners`).
- `D103`: fixtures with an empty `realizes: []`.
- `D104`: fixtures using block-style YAML lists (not recognized as a
  list at all) — also added a standing self-check (lint the fixture
  before exercising real behavior), which paid off immediately at the
  next round. A **sandbox-contamination bug in the bootstrap driver
  itself** was also found and fixed here: dependency/spec directories
  were symlinked into the sandbox rather than copied, so one test's own
  synthetic fixture (`AC-ASSEMBLE-005`) wrote through the symlink into
  the real repo (`specs/components/zz-lint-broken-fixture/`, untracked,
  removed, no history contamination) and silently polluted every
  subsequent sandbox's corpus. Fixed: `copytree`, not `symlink_to`.
- `D105`: `status` enum stated literally (not just "required"); the
  frontmatter rule applies to `VAR-*.md`/`D<N>.md` too, not just
  `component.md`; every `requirements/` file needs a matching
  `acceptance/` file.
- `D106`: a *second*, independent `CriterionBundle` producer
  (`verifier-orchestrator`'s own internal bundle-builder, used for
  self-verification) predates `dependency_interfaces` and crashed
  `author_test` outright on a missing attribute — fixed by making
  bundle field access tolerate a missing field, not by changing
  `verifier-orchestrator` (tracked separately, not fixed).
- `D107`: fixtures using `status: ratified` without the
  `last_ratified_commit` field `R-LINT-002` requires alongside it.
- `D108`: the real backend call forwarded `seed` as a keyword
  argument; `llm_endpoint.complete()` forwards every kwarg verbatim
  into a CLI flag, and `--seed` isn't one the backend CLI recognizes —
  every real (non-mocked) call failed identically, invisible in the
  hand-maintained suite's mocked tests. Diagnosed by reproducing
  `complete()`'s real call directly, outside the harness, with and
  without the extra kwarg.

**Root-cause diagnosis in an isolated sandbox was essential throughout**
— every failure above was found by directly linting or executing a
failing criterion's own synthetic fixture (or the real backend call)
in isolation, in a throwaway sandbox, never by patching the rejected
candidate. This is what made it possible to tell "the candidate is
wrong" apart from "the test written against it is wrong" at each step;
in every instance across this whole arc, the candidate itself was never
the one at fault.

**Final result: 11 of 14 criteria pass** (`claude-opus-5-5`, swapped
in `D109`). Three known limitations, not chased further:

- `AC-ASSEMBLE-013` (3 sub-tests): synthetic fixtures leave trailing
  whitespace on lines, tripping `R-LINT-019` — the same "fixture isn't
  actually lint-clean" problem class as `D102`-`D107`, a new instance.
- `AC-ASSEMBLE-011`: two synthetic components are non-sealed with no
  `realizes`, tripping `R-LINT-006` — `R-AUTHOR-013`'s sealed-by-default
  instruction is a SHOULD, not consistently followed by the model.
- `AC-ASSEMBLE-010`: not a bug — `component_context`'s own interface
  doc documents its `purpose` column as "verbatim," and its regex
  naturally includes a trailing newline; the AC's Gherkin asks for an
  exact match that didn't anticipate that, so the candidate's
  `'Caches results.\n'` is arguably correct against the real
  dependency's own documented contract.

The old hand-written `test_spec_bundle_assembler.py` (and its
`conftest.py`) are retired, superseded by the new per-criterion
`generated-test` files — confirmed incompatible with the new
candidate's own naming (`PreconditionFailureError` renamed
`PreconditionFailure`), and its one test without a direct `AC-id`
match (a sealed dependency's `source_path` resolution) is covered
inside the new `AC-ASSEMBLE-011` fixture too.

## Second cold-generation round (`D114`–`D118`)

`provenance-tracker`'s own bootstrap hit, for real, a gap deferred
twice already (`D110`, `D112`): `dependency_interfaces` never
resolved a type a dependency's own signature references but a
different, undeclared component owns (`provenance-checker`'s
`verification_report` field names `VerificationReport`, owned by
`verifier-orchestrator`, which `provenance-checker` correctly never
depends on). `D114` closed this directly: `R-ASSEMBLE-013` resolves
any such bare type name one level deep, searching the whole corpus
for its real, unambiguous owner.

The real retry against this fix passed the new `AC-ASSEMBLE-015`
directly on the first try, but regressed three previously-passing
criteria (`AC-ASSEMBLE-006`/`011`/`013`) on one shared cause: synthetic
fixtures gave `constraints.md` a frontmatter block, which `R-LINT-016`
rejects — closed by `D115`, stating the opposite rule (`a unit file
carries none at all`) in `R-AUTHOR-012` just as explicitly as the
"these fields are required" rule it had over-applied.

The next retry surfaced a real, pre-existing documentation gap in
`spec-linter`'s own `interface/library.md` (`lint()`'s real signature
accepts `paths: list[Path] | None`, not a bare required list, and a
`judge` parameter neither one the doc ever mentioned) — fixed
directly with no regeneration (`D116`, `spec-linter`'s code was
already correct). The corrected signature alone was not reliably
sufficient — `D117` closed the gap fully by giving `R-AUTHOR-015`'s
self-check a literal worked call (`lint(None, repo_root)`) rather
than prose describing the signature.

**Final result: 14 of 15 criteria pass** (`D118`), up from the first
round's 11 of 14. The one remaining failure, `AC-ASSEMBLE-011`, is not
a test-authoring or candidate defect: its self-check correctly calls
`lint()` against a fixture with zero decision files, which trips
`graph-query-engine`'s own `_FRONTMATTER_ZERO_MATCH_GUARDS`
substitution into a malformed query — confirmed via
`graph-query-engine`'s own hand-maintained suite failing identically
and predating this entire session. A known limitation in an
already-stable, out-of-scope component, not chased here.
`AC-ASSEMBLE-007`'s prior known limitation (`D109`) did not
re-trigger this round.

## `D177`: `AC-ASSEMBLE-011`'s real cause, and two failed attempts to fix it

The failure recorded in `D118` as a `graph-query-engine` gap was a
defect in the generated test itself: it builds each fixture
`component.md` with `textwrap.dedent` over an f-string that interpolates
a multi-line value, leaving `---` indented, so the file has no
frontmatter and `lint()` fails. Repairing only that indentation in a
scratch copy makes the test pass against the unchanged code.

Two attempts to replace the test failed. A full regeneration (seed 11)
failed 14 of 15 criteria: the new tests statically imported
`spec_linter`. Authoring `AC-ASSEMBLE-011`'s test alone four times
(seeds 41-44), after its criterion gained an exact fixture recipe,
produced two collection errors from the same static import and two
assertion failures. Nothing was swapped in. A fix belongs in
`test-author`'s spec (never import a dependency by name; never `dedent`
an interpolated multi-line value). Until then `AC-ASSEMBLE-011` fails.
