# Bootstrap Account: `provenance-writer`

Cold-generated, not hand-written — a real model call, through a real
`generator` dispatching through a real `llm-endpoint`, from this
component's own assembled spec bundle and nothing else, with real
`test-author`-authored criterion tests and real `verifier-orchestrator`
mutation scoring. Landed at 17 of 17 criteria passing,
`mutation_score=0.8` (exactly at the bar) — the cleanest multi-round
landing this session: every round's failure was a single, precisely
diagnosed root cause, never noise chased blindly.

## Round 1 (`D128`): inputs itself needs dual access too

First real attempt: 6 of 12 criteria passed, `mutation_score=1.0`. All
six failures crashed identically: `build_manifest`'s own top-level
reads of `inputs` (`inputs.generation_result`,
`inputs.license_scan_result`, ...) were bare attribute access, even
though the candidate's own `_field()` helper already applied dual
dict-or-attribute access correctly to every field *nested inside*
those values. Every failing criterion's test happened to construct
`inputs` as a plain dict; every passing one either wrapped its dict in
an attribute-forwarding shim or built a real `ProvenanceInputs`
instance. The identical bug class `R-TRACK-012` already closed for
`provenance-tracker`, one level removed: there, a *called*
dependency's return value read bare; here, a parameter the *caller*
hands in directly, read bare. New `R-PROV-014` states it explicitly.

## Round 2 (`D129`): write-time window truncation (test-author)

Second attempt against `R-PROV-014`: 11 of 14 passed (the fix landed
clean), `interface_drift=True` (the candidate added an undocumented
`now` keyword parameter — a one-off mistake, not retried with
specific feedback since the general interface-drift rule already
covers it and it didn't recur). One real test-authoring gap:
`AC-PROV-008`'s test captured its own `before`/`after` write-time
window at full microsecond precision while `generated_at`'s
documented format (`interface/data/provenancemanifest.md`'s own
example) is whole-seconds-only — a correctly implemented candidate
fails this comparison on almost every real run. Closed in
`test-author`'s own spec and `BOOTSTRAP.md` (`D129`, `R-AUTHOR-023`,
round 20 there) — not specific to `provenance-writer`, any future
wall-clock "own write time" field can hit the identical shape.

One other failure this round (`AC-PROV-002`, a `fake_signature_mismatch`
against an unused `cache-manager.get` fake neither the scenario nor
the candidate's own code ever calls) was treated as one-off model
noise on a component shape this corpus hadn't exercised before (a pure
aggregator with an otherwise-inert `depends_on`) and did not recur on
retry.

## Round 3 (`D130`): the CLI entry point had zero coverage

Third attempt, after `test-author`'s `R-AUTHOR-023` fix: 14 of 14
criteria passed behaviorally, `interface_drift` back to `False` (the
stray `now` param did not recur). `verify()` still failed:
`mutation_score=0.57`. Diagnosed directly by running the real mutation
harness's own mutant generator against the candidate: 8 of 14 mutable
nodes exist only inside `main()`/`_parse_args()` or the
`if __name__ == "__main__":` guard — code no criterion's test ever
calls, since every one of them exercises `write_provenance`/
`build_manifest` as a library call. Root cause: `interface/cli.md`
documents a real CLI but no requirement or acceptance criterion had
ever covered it — a genuine pre-existing spec gap, not a candidate
defect. New `R-PROV-015`/`AC-PROV-015` state `main`'s exact behavior
per `cli.md` (exit `0`/`1`/`2`) and test every exit path.

## Round 4 (`D131`): _to_jsonable needs the full D94 shape range

Fourth attempt against `R-PROV-015`: `mutation_score=1.0`, 14 of 15
passed (`AC-PROV-015` itself passed cleanly, confirming the CLI gap
closed). One failure: `AC-PROV-007` crashed with `TypeError: Object of
type SimpleNamespace is not JSON serializable`. The test built
`license_scan_result`/`secret_scan_result` as `SimpleNamespace`
instances — a legitimate shape under this corpus's `D94` duck-typing
convention — but the candidate's `_to_jsonable` only special-cased
`dict`/`list`/`tuple`/`dataclasses.is_dataclass()`, falling through to
return anything else unchanged. A different operation from
`R-PROV-014` (reading a field off a value) — this is *serializing* an
already-read nested value, needing the same shape range on the way
out. New `R-PROV-016` closes it.

## Round 5 (`D132`): ProvenanceInputs must stay a real class

Fifth attempt against `R-PROV-016`: `mutation_score=1.0`, but 8 of 16
failed, all with the identical `AttributeError: module
'provenance_writer' has no attribute 'ProvenanceInputs'`. This round's
candidate correctly implemented dual access throughout but, reasoning
that duck-typing made a concrete class unnecessary, dropped
`ProvenanceInputs` entirely — breaking every test that constructed one
by name, matching `interface/data/ProvenanceInputs.md`'s own
documented type and the universal (if previously unstated) corpus
convention that every component with a documented `interface/data/`
type defines it as a real dataclass (`cache-manager`'s `CachedResult`,
`license-scanner`'s `LicenseScanResult`, `secret-scanner`'s
`SecretScanResult`). New `R-PROV-017` states this directly: dual
access and a real, constructible class are not in tension — the class
is an additional, always-present construction path, not a replacement.

## Round 6: landed

Sixth attempt against `R-PROV-017`: all 17 of 17 criteria pass,
`mutation_score=0.8` — exactly at the bar, no averaging artifact (the
`D124` union fix continuing to do real work: a genuinely well-tested
component scores accordingly). Swapped in. `model_pin` set to
`claude-sonnet-5`.

Added `verification/provenance-writer/conftest.py` (missing from the
swap, same gap found for `spec-bundle-assembler` and
`provenance-tracker` earlier this session) so the suite runs standalone
with plain `pytest`; the sandboxed driver itself now creates this file
automatically on every future swap, closing the gap at its own root
rather than leaving it to recur a fourth time.

Blast radius checked (`D99`): `corpus-graph-builder` is the only
already-built dependent; its own suite (8/8) passes unchanged.
`component-gate-runner` is also a dependent but not yet built.

## `D170`/`D173`: the sealed provenance manifest

Regenerated to add `write_sealed_provenance` and the `SealedProvenance`
schema it owns (`R-PROV-018`/`019`): a sealed component's own provenance
file, defining its ownership. Eight rounds, landing at 20 of 20
criteria, `mutation_score=0.87`. The sealed requirements themselves
passed on the first round; the rest were gaps the new code exposed:

- Two older criteria let test authors guess. `AC-PROV-014`'s test
  found manifests with `glob("*.provenance.json")`, which never matches
  a hidden `.provenance.json` (and the same glob then broke
  `AC-PROV-004`, so the rule moved into `interface/library.md`).
  `AC-PROV-015` named no missing field, and my first fix called a null
  `verification_report` optional, which was wrong: the data document
  makes it null only when nothing was generated, so a null report beside
  generated files is missing input.
- `interface/cli.md` never said what `main` receives. The dispatcher
  keeps these verb words, so it is `["provenance", "write", ...]`.
- Two rounds were lost to the model backend's usage limit, not the spec.
- With every criterion passing, mutation testing scored 0.67: the sealed
  validator's per-field type checks and older uncovered behavior
  (rewriting an existing manifest, the `--repo-root <dir>` form, an
  object with a method) had no tests. `AC-PROV-020`/`021` and extensions
  of `AC-PROV-015`/`016` cover them, and the criteria-entry `result`
  rule is now stated.

56 of 56 tests pass in this directory.
