# Bootstrap Account: `verifier-orchestrator`

Cold-generated, not hand-written — a real model call, through a real
`generator` dispatching through a real `llm-endpoint`, from this
component's own assembled spec bundle and nothing else. The first
three real generation attempts (predating this file) each failed for
a genuine, previously undocumented spec gap — how a dependent locates
a sealed sibling module; interface-drift's exact scope (`D84`); a
result field's required type (`D85`) — fixed at root cause before
retrying, never patched by hand. All thirteen `AC-VERIFY-*` criteria
pass against the hand-maintained suite
(`test_verifier_orchestrator.py`) once landed.

Every `AC-VERIFY-*` file declares `Kind: generated-test`, directly
contradicting `component.md`'s own "Acceptance criteria" section,
which claims all thirteen are `kind: compiled`. A real, pre-existing
inconsistency — not resolved here (`D119`'s own context), and not
load-bearing for this component's own verification, which always runs
against the hand-maintained suite directly rather than through a
self-verifying `bootstrap_component.py` cycle (the same `D58`-style
exemption `test-author` uses, for the same reason: this component
implements `verify()` itself, so using it to verify itself is
circular).

## Round: dependency_interfaces fix (`D119`, `D120`)

Chasing `provenance-tracker`'s own recurring, real test-authoring
failures (wrong-arity and wrong-shape dependency fakes, even after
`test-author`'s own `R-AUTHOR-011`/`R-AUTHOR-020` fixes) led to
checking what `dependency_interfaces` `test-author` actually receives
during a real `bootstrap_component.py` run: always empty. This
component's own `_build_criterion_bundle()` built a second,
independent `CriterionBundle` with no `dependency_interfaces` field at
all — a producer `D106`/`D112` already flagged as a deferred,
tracked gap, now confirmed as the real root cause behind every
dependency-shape-guessing failure any real component hit this session,
not only `provenance-tracker`'s.

This was never actually a spec gap: `R-VERIFY-009` already said to pass
"exactly the `CriterionBundle` spec-bundle-assembler produces" — the
real candidate had simply never implemented that, and `depends_on`
was never amended to list `comp-spec-bundle-assembler` either. `D119`
closed this directly: `depends_on` gains the missing dependency,
`R-VERIFY-009` states the prohibition on a second `CriterionBundle`
explicitly, and the hand-maintained suite gained a new fixture
(`comp-bar`, a real dependency with a documented interface) and test
proving `dependency_interfaces` now carries real content.

The first real regen against this fix passed the new test directly,
but regressed `AC-VERIFY-004` (interface drift). Calling the drift
check directly, outside `verify()`, with the identical fixture, proved
the check's own logic was correct — the real cause was
`load_component_module`'s own `sys.modules[module_name]` cache, keyed
by bare name only: every hand-maintained test uses slug `"foo"`
against its own fresh `tmp_path`, and a later test's call silently
reused an *earlier* test's cached module. The identical bug class
`R-TRACK-011` already closed for `provenance-tracker`'s own loader.
Closed by `D120`: `R-VERIFY-013` requires every cache keyed by
`(repo_root, module_name)`.

The next real regen against both fixes together passed all 14 cases
(13 original plus the new dependency_interfaces test) directly.
Swapped in. `model_pin` set to `claude-sonnet-5` (not previously
pinned).

Blast radius checked (`D99`): `corpus-graph-builder` is the only
already-built dependent; its own suite (8/8) still passes unchanged.
`component-gate-runner`/`provenance-writer` are also dependents but
not yet built.

## Round: mutation-score union fix (`D124`)

With `D119`–`D123` landed, `provenance-tracker` finally reached 7/7
real criteria passing — but `verify()`'s separate mutation-score gate
still failed, consistently, at 0.04–0.14 against an 0.8 bar,
regardless of test quality. Diagnosis: this component's own mutation
testing scored each `generated-test` criterion's test file in
isolation against mutants anywhere in the whole candidate module,
then averaged the per-criterion scores — `provenance-tracker` has
three behaviorally distinct entry points, and a criterion whose own
Gherkin covers only one of them has no way to kill a mutant in a
sibling function. `interface/data/VerificationReport.md` already
documents `mutation_score` as one number per component, never one per
criterion, confirming the averaging approach was never the intended
design. Confirmed structural, not specific to `provenance-tracker`,
with a new minimal two-function fixture in this suite
(`do_the_thing`/`double_it`, each with its own passing, fully-covering
test): the old algorithm scored 0.25 regardless.

Closed by `D124`: `mutation_score` is now a union across all of a
component's own `generated-test` criteria's tests — a mutant counts
as killed if *any* of them fails against it. The new fixture now
scores above the bar with the same tests unchanged. 15 of 15 cases
pass directly, including the new union-scoring test. Swapped in.
