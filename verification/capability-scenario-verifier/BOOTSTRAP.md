# Bootstrap Account: `capability-scenario-verifier`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D42`), through two real spec fixes
(one of them a sealed-dependency extension and a cross-cutting fix to
`spec-bundle-assembler`) and three `generate()` calls.

**Call 1** produced a well-documented candidate (it explicitly flagged
its own "implementation assumptions" as distinct from spec content —
a good discipline on its own part) with two real bugs: it looked for
capability scenarios under a nonexistent `specs/capabilities/`
directory (they actually live as `### CS-<id>` sections embedded in
each capability's own `specs/product/<name>.md`), and it called
`criterion-compiler`'s directory-scanning `compile()` for `kind:
compiled` dispatch — which can never work for a capability scenario,
never scoped to any one component's `acceptance/`. Fixing the second
bug required extending `criterion-compiler` itself (sealed,
hand-authored): a new `compile_criterion(criterion, surface=None)`
primitive, `compile()` now implemented in terms of (`D59`). Not
swapped in.

**Call 2**, with both fixes in place, correctly used `compile_criterion`
and the right capability-scenario location — but its dynamic loader
assumed `criterion-compiler` lives under `gen/criterion-compiler/`,
like every non-sealed dependency. It doesn't: `criterion-compiler` is
sealed, with real code at `pipeline/criterion-compiler/`. Checked
directly: `spec-bundle-assembler`'s `dependency_usage` only ever
looked under `gen/`, so every sealed dependency's usage card had
silently degraded to empty — the same empty string a dependency with
no real code at all produces, indistinguishable from each other.
Fixed in `spec-bundle-assembler` directly (`D60`): checks a
dependency's own `component.md` for `sealed: true` + `source_path`
first. The same call also reproduced an *already-seen* bug from call
1's own design space: its `realizes`-edge fallback scanned capability
files for a `realizes:` field that only ever exists on *component*
files. Reproducing the identical bug independently confirmed a real
spec ambiguity, not a one-off mistake; `R-SCENARIO-002` now states the
correct direction explicitly (`D61`). Not swapped in.

**Call 3**, with all three fixes in place, correctly resolved
`criterion-compiler` from its real sealed location, correctly scanned
component files for `realizes:`, and made a reasonable, explicitly-
documented design choice for the one thing nothing authoritative has
pinned down yet: `judge`/`test_author`'s exact injected-callable
signature (`verifier-orchestrator`, the component that would set this
precedent, doesn't exist yet) — a single-argument `fn(bundle) ->
result` callable. Verified against all 3 `AC-SCENARIO-*` criteria for
real. Swapped in.

## `D174`/`D175`: `run_capability_gates`, finally built — and scenarios actually run

`R-SCENARIO-004` (`D89`) required `check_capability_provenance` and
`run_capability_gates`; the module generated before it never had them,
and its tests, which predated the requirement, kept passing. An audit
before regenerating found more (`D174`): three conflicting signatures
for one function, scenarios marked `pass` once a test was produced or
compiled rather than run, a bundle `test-author` could not accept, and
a capability with no scenarios reporting `pass`. The spec was rewritten
first (`R-SCENARIO-005`–`008`, twelve criteria, `interface/cli.md`
removed), then regenerated.

Five build rounds, landing at 12 of 12, `mutation_score=0.84`:

- **Round 1** passed 1 of 12. Eleven failures shared one cause: the
  fixture rules lived in one criterion, but a test author sees only its
  own criterion, the requirement it covers, and `interface/`. The rules
  moved to `interface/library.md` ("Test fixtures").
- **Round 2** passed 10 of 12. The candidate was right and two criteria
  were impossible: a `compiled` capability scenario cannot pass (the
  compiler asserts on a `result` that only a `When` step defines, and a
  `When` cannot resolve with `surface=None`). The old hand tests had only
  "passed" because compiling counted (`D175`). Two further rounds were
  lost to backend errors, and one to the model quota.
- **Round 4** passed 10 of 12: a fake `author_test` read `scenario_id`
  where the real wiring passes `criterion_id`, and a fixed absolute path
  in a criterion (`/tmp/escape.py`) was written by a mutant that disabled
  the path guard, failing the next run. Both fixed in the spec/criteria.
- **Round 5** landed.

The obsolete hand-written `test_capability_scenario_verifier.py` was
removed: it asserted the pre-`D174` behavior and failed two tests against
the new module. `conftest.py` is reduced to the path setup.
