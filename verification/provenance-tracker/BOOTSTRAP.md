# Bootstrap Account: `provenance-tracker`

Cold-generated, not hand-written — a real model call, through a real
`generator` dispatching through a real `llm-endpoint`, from this
component's own assembled spec bundle and nothing else, with real
`test-author`-authored criterion tests (never hand-written) and real
`verifier-orchestrator` mutation scoring. Landed at 5 of 7 real
criteria passing with `mutation_score=1.0` (`D127`). Both remaining
failures are documented known limitations, confirmed via direct
sandbox inspection rather than accepted at face value.

## Round: foundational shape fixes (`D95`, `D98`, `D99`, `D100`)

The earliest cold-generation rounds surfaced four genuine, previously
undocumented gaps, each fixed at root cause before retrying:
`last_requirement_failures`'s real `requirement_results` shape stated
directly (`D95`); lazy dependency loading stated explicitly for both
`check_readiness` dependencies, since an earlier real candidate loaded
`impact-analyzer` unconditionally twice despite this already being
implied by *when* it is called (`D98`); a blast-radius-before-
committing workflow MUST, so a developer never discovers a wide blast
radius only after already committing (`D99` — also the origin of the
standing "check blast radius before any swap" workflow this whole
session followed for every other component); `AttemptRecord`'s
in-memory shape stated directly (`D100`).

## Round: dependency-loading correctness (`D111`, `D121`, `D122`)

Found via symlink-free sandbox testing, not the hand-wavier earlier
rounds: `check_readiness` must resolve dependency modules relative to
`repo_root`, never file-location-relative, never cached in
`sys.modules` by bare module name alone — the same bug class later
also found and fixed in `verifier-orchestrator`'s own loader (`D120`,
`R-VERIFY-013`). Closed by `D111`, `R-TRACK-011` (self-corrected
within the same decision after an embedded wording ambiguity — the
package-shape path description was missing the `<module_name>/`
subdirectory level, also fixed in `test-author`'s `R-AUTHOR-010` for
the identical ambiguity).

`D121`, `R-TRACK-012`: `check_readiness` must use dual
dict-or-attribute access reading any dependency's return value
(`result.hit`/`result["hit"]`, `entry.component_id`/
`entry["component_id"]`), never bare attribute access. Found only
once `D119`'s `dependency_interfaces` fix (below) let `test-author`
build accurate, correctly-shaped fakes for the first time — every
earlier, wrong-shaped fake had been masking this bug by accident,
since a wrong-arity or wrong-shape fake failed before the candidate's
bare-attribute access ever ran.

`D122`: `R-TRACK-010` amended to state exactly how the `realizes` edge
is computed — scanning every `specs/components/*/component.md`'s own
`realizes:` field, never a nonexistent reverse-pointer on
`specs/product/<name>.md`. Found once a candidate scanned a
nonexistent `specs/capabilities/` directory with a backwards edge
convention, mirroring `capability-scenario-verifier`'s own internal
(never-exposed) `_collect_realizes_edges` convention — the same fix
this component's own real code now also implements directly.

## Round: the `dependency_interfaces` root cause (`D119`, `D120`)

Repeated dependency-shape-guessing test-authoring failures (wrong
arity, wrong return shape) at every seed traced to a real, systemic
cause entirely outside this component: `dependency_interfaces` was
*always* empty for every criterion authored via
`bootstrap_component.py`'s `verify()` call path, because
`verifier-orchestrator`'s own `_build_criterion_bundle()` built a
second, independent `CriterionBundle` with no `dependency_interfaces`
field at all — a gap `D106`/`D112` had already flagged as deferred but
never fixed. Closed in `verifier-orchestrator`'s own `BOOTSTRAP.md`
(`D119`, `D120`); full account there. Once landed, retrying this
component jumped from a stable 3/6 to 6/7, then 7/7 behaviorally.

## Round: mutation-score design gap (`D123`, `D124`)

`D123`, `R-AUTHOR-022`: tests must never assert fake usage via a
guessed `sys.modules` key, since real loaders key dynamically and
hash-qualified; must rely on the fake's own recorded invocation list
instead. Found recurring at two different seeds with the identical
symptom.

`D124`: even with all seven criteria behaviorally correct,
`verify()`'s own mutation-score gate stayed stuck at 0.04–0.14 against
an 0.8 bar, for every seed, regardless of test quality — this
component's own three distinct entry points (`write_attempt_record`,
`last_requirement_failures`, `check_readiness`) structurally depressed
an averaged per-criterion mutation score. Root cause and fix (a union
across all of a component's own tests, never an average) belong to
`verifier-orchestrator`'s own `BOOTSTRAP.md`; full account there.
Once landed, `mutation_score=1.0` on every subsequent round for this
component.

## Round: `run_capability_gates` naming and third-party imports (`D125`)

After the mutation-score fix, 6/7 behaviorally passing with one
recurring failure at two different seeds: the candidate called
`capability_scenario_verifier.run_capability_scenarios` instead of the
spec-mandated `run_capability_gates`. `R-TRACK-010` amended with the
literal worked call (`run_capability_gates(capability_id, repo_root,
judge=judge, test_author=test_author)`), explicitly naming the wrong
sibling function to avoid — prose alone naming the right function was
not reliably sufficient, matching the "worked snippet beats prose"
lesson from earlier in the session.

Same decision: `R-AUTHOR-012` amended (test-authoring, not this
component's own spec) after a generated test hit `ModuleNotFoundError:
No module named 'yaml'` — tests must never import an unavailable
third-party package, generalizing the identical `D101`/
`R-ASSEMBLE-012` lesson from `spec-bundle-assembler`'s own candidate
code to test-authoring itself.

## Round: alias-arity resolution (`D126`)

Regenerating `test-author` against `D125` surfaced a genuine
regression in its own fake-arity check: alias detection
(`name = other_name`) worked, but every detected alias was then
explicitly skipped rather than resolved to its target's real arity —
so the one name a real dependency signature actually references was
never checked at all. Closed in `test-author`'s own `BOOTSTRAP.md`
(`D126`, `R-AUTHOR-020`); full account there.

## Round: landing at 5/7 (`D127`)

After `D119`–`D126` all landed, a final retry (seed 4,
retry-feedback citing `R-TRACK-010`) reached `mutation_score=1.0` and
5/7 (`AC-TRACK-004/007/008/011/012` pass; `AC-TRACK-009`/
`AC-TRACK-010` fail). Both remaining failures were diagnosed by
calling `check_readiness` directly against each failing test's exact
fixture, outside pytest, rather than accepted at face value:

- **`AC-TRACK-009`** — a real, minor gap in the candidate itself.
  `R-TRACK-009` requires `not_ready_reasons` to name "which component,
  which check failed." The candidate's message for a failing hit is a
  single generic string ("provenance hit but verification/scan not
  passing") regardless of whether `verification_report`,
  `license_scan`, or `secret_scan` was the actual cause, and never
  names the specific failing requirement id the test expects
  (`R-FAILCHECK-001`). `ready=False` and the component name are both
  still correctly surfaced.

- **`AC-TRACK-010`** — a test-authoring fixture bug, not a candidate
  bug. Both failing scenarios' `check_capability_provenance` fixture
  returns `hit=True` unconditionally, including the two scenarios
  ("all components and capabilities pass" and "one capability's run
  fails") that are meant to exercise `run_capability_gates`'s result.
  Per `R-TRACK-010`'s check-then-run design, a `hit=True` from
  `check_capability_provenance` is a deliberate short-circuit —
  confirmed directly: calling `check_readiness` against each fixture
  returns the check-then-run-correct result in both cases, since the
  injected failure lives inside `run_capability_gates`, which the hit
  makes unreachable. The fixtures needed `hit=False` to route through
  `run_capability_gates` at all. This is a reusable test-authoring gap
  (any check-then-run dependency shape can hit it again, and this
  corpus has at least one other instance of the convention in
  `provenance-checker` itself) but is left undocumented in
  `test-author`'s own spec for now rather than adding a new
  requirement under its `R-LINT-012` word budget, already trimmed
  several times this session.

Given `D95`–`D127` already spans 33 decisions for this one component,
both are recorded here as known limitations rather than chased
further. `model_pin` set to `claude-sonnet-5`.

Blast radius checked (`D99`): `component-gate-runner`,
`provenance-tracker-ui`, and `review-packet-builder` all depend on
`comp-provenance-tracker`, but none is yet built — nothing to
re-verify.

## `D163`: the canonical provenance key, and both known limitations closed

Regenerated after an audit found this component computed its own
`spec_bundle_hash`, different from the one `generator` and
`provenance-writer` record, and always supplied `gate_versions` `{}`:
no `.provenance.json` a real `hotdocs generate` wrote could ever have
been a hit here. It now calls `provenance-checker`'s
`current_provenance_key` (`R-TRACK-009`). The spec also now closes
both `D127` known limitations: `not_ready_reasons` names the failing
check and requirement ids, and `AC-TRACK-010` states that a
`run_capability_gates` scenario needs a capability miss. Round 1 passed
six of seven; the seventh failed on a fixture directory named
`comp-widget`, resolved by reading each component's id from its
frontmatter. Round 2 landed at 7 of 7, `mutation_score=1.0`, and the
three previously failing tests in this directory pass.
