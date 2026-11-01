# Bootstrap Account: `test-author`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D58`), through two real spec fixes and
four `generate()` calls (one a deliberate plain retry, forced past a
legitimate cache hit).

**Call 1** set `GATE_VERSION = "test_author@v1"`, reasonably mirroring
`generator`'s own pattern where the `gate_version` prefix equals the
component's own name — but `cache-manager`'s six-entry `gate_type`
registry has no `test_author` entry; the real one for this kind of
artifact is `generated_test`. Crashed on its own first cache write.
Fixed by clarifying `R-AUTHOR-004` explicitly (`D72`). Not swapped in.

**Call 2**, with that fix in place, implemented exactly
`interface/library.md`'s then-documented signature —
`author_test(bundle, model, seed=0)` — which never declared an
injectable backend at all, despite every `AC-AUTHOR-*` criterion's own
Gherkin requiring "a mock model." A genuine interface gap, not a
candidate mistake: `generator`'s own `library.md` already documents an
`llm_backend` parameter for exactly this reason; `test-author`'s never
did. Fixed by adding it explicitly, mirroring `generator`'s parameter
name (`D73`). Not swapped in.

**Call 3**, with both fixes in place, correctly added `llm_backend`
and the right `gate_version` — but its dependency loader's
flat-module fallback checked `gen/<slug>.py` (a sibling of `gen/`
itself) instead of `gen/<slug>/<module>.py`, an asymmetric bug: the
*package*-loading branch right above it checked the correct nested
path. A plain implementation defect, not a spec gap. Deleted, not
swapped in.

**Call 4** (a plain retry) returned the *same* call-3 candidate from
cache — correctly, since nothing about the component's own `SpecBundle`
had changed between attempts and the cache key doesn't know a human
rejected the cached result for a reason outside the key. Forced a
genuinely fresh call by deleting that one specific stale cache entry
directly, confirmed first by inspecting its payload. The resulting
candidate correctly nests the flat-module path. Verified against all
8 `AC-AUTHOR-*` criteria for real. Swapped in.

One operational hazard found and fixed during the swap itself: an
earlier `rm -rf gen/test-author` + a cache-hit replay before the
final fix left a stale `test_author/` *package* directory sitting
alongside the final flat `test_author.py` module — Python's import
machinery silently preferred the stale package, making tests run
against rejected code without erroring. Caught by a failing traceback
that still named the old (rejected) module's internal structure.
Fixed by removing the whole `gen/test-author/` directory and
recreating it with only the final candidate's one file.

## Round 2 (`D94`): nonce-delimited output protocol

The first real, non-mocked `author_test` call against a genuine
downstream criterion — bootstrapping `provenance-tracker`, the first of
the seven still-unbuilt components — surfaced a real gap invisible to
every `AC-AUTHOR-*` criterion's own mocked-backend verification: the
prompt said only "Output only the test code," with no reliable
extraction step on the receiving end. Against five real criteria, this
produced a markdown-fenced response once and four partial transcripts
of an attempted (and blocked) tool call the rest of the time, since
nothing told the model it has no tool or file access.

Fixed in the spec first (`R-AUTHOR-009`, `D94`): the same per-call
nonce-delimited BEGIN/END marker format `generator` already uses
(`D38`), plus an explicit no-tool-access instruction. One real
`generate()` call against the updated spec bundle produced a candidate
that correctly implements both — markers, strict between-marker
extraction (discarding any fence/narration outside them), and a
distinct `malformed_response` outcome (file `None`, nothing cached or
written to disk) when a response has no matching marker pair. Also
drops this component's own redundant `CriterionBundle` class in favor
of a bare duck-typed `bundle` parameter — not itself required by
`R-AUTHOR-009`, but a reasonable simplification consistent with the
corpus's general plain-value cross-component convention (the same
reasoning `R-TRACK-004` states for `provenance-tracker`), so the hand-
maintained `AC-AUTHOR-*` test suite's fixture now builds a
`SimpleNamespace` instead.

The hand-maintained `verification/test-author/test_test_author.py`
suite (the same mocked-backend verification exception `D58`'s bootstrap
already established for this component, since nothing else can verify
`test-author` without it already working) was updated: every mock
response now wraps its content in the real marker format via a shared
`file_block` conftest helper that reads the nonce back out of the
prompt actually sent, and two new cases cover `AC-AUTHOR-009` directly
(stripping a fence-and-narration wrapper around the markers; a
no-marker-pair response treated as a distinct failure with nothing
cached or written). All 10 test cases (the original 8 `AC-AUTHOR-*`
criteria plus 2 covering the new `AC-AUTHOR-009`) pass against the new
candidate. Swapped in; the pre-fix candidate is not kept.

## Round 3 (`D96`): dependency-resolution convention

`provenance-tracker`'s own re-verification against the round-2
candidate above still failed three of five `AC-TRACK-*` criteria, all
for the same underlying reason despite round 2's protocol fix working
correctly: nothing told the model that this corpus's components
resolve each other dynamically at runtime, never via a name Python's
own import system or `unittest.mock.patch` could find statically. One
authored test guessed a nonexistent package-submodule import path;
two assumed dependencies were patchable by name; the one that did
correctly reproduce the real dynamic-loading shape for the component
under test omitted the one correctness-critical `sys.modules`
pre-registration step — the same specific pitfall this corpus's own
real loaders (`generator`, `test-author` itself, `provenance-tracker`)
already had to learn the hard way once each.

Fixed in the spec (`R-AUTHOR-010`, `D96`): a fixed, always-included
instruction stating the convention plus a literal worked snippet
(prose alone already proved insufficient once). One real `generate()`
call against the updated spec bundle produced a candidate whose prompt
correctly includes the full convention text and worked snippet,
verbatim, via a module-level `DEPENDENCY_CONVENTION_INSTRUCTION`
constant. `PROMPT_VERSION` → `v3`; `file`/`model_call_error` are now
plain dicts again (this round's own reasonable representation choice,
not itself required by any requirement). The hand-maintained
`AC-AUTHOR-*` suite was updated for the dict shape and gained
`AC-AUTHOR-010`, asserting the convention text, path pattern, and
correct snippet ordering all appear in the real prompt sent. All 11
test cases pass against the new candidate. Swapped in; round 2's
candidate is not kept.

## Round 4 (`D97`): narrowing round 3's own new instruction

`provenance-tracker`'s own retry against round 3's candidate (forced by
`D95`'s separate spec change, which touched every criterion's assembled
bundle) got `AC-TRACK-004`/`007` passing cleanly, but surfaced two
narrower problems with round 3's own new convention instruction:
`AC-TRACK-008`'s authored test read the instruction's unqualified
opening sentence as applying to importing the component under test
itself, and — with no worked example for the package case — wrote its
own ad hoc loader that got the path wrong; `AC-TRACK-009`'s authored
test correctly limited the technique to a genuine dependency, but tried
to fake it in the package shape (writing to `gen/<slug>/__init__.py`
directly, with "__init__" standing in as a literal module name) since
the prior worked snippet only ever demonstrated the flat-module case —
landing on a path no real loader in this corpus checks.

Fixed in the spec (`R-AUTHOR-010` narrowed in place, `D97`): the
instruction now states explicitly that it governs faking a dependency
only, explicitly tells the model the component under test itself needs
a plain import and no custom loader at all, and narrows the
fake-writing recipe to always the flat-module shape with `module_name`
spelled out precisely. One real `generate()` call produced a candidate
whose prompt correctly separates "import the component under test
plainly, no loader" from the dependency-faking convention, and states
the flat-only rule unambiguously. `PROMPT_VERSION` → `v4`; this round
also drops the module-level `DEPENDENCY_CONVENTION_INSTRUCTION`
constant in favor of inlining the text directly in `_build_prompt` — a
reasonable representation choice, not itself required by any
requirement, so the hand-maintained suite's `AC-AUTHOR-010` assertions
were updated to check substrings of the real prompt text (normalized
for incidental line-wrapping) rather than importing an exported
constant. All 11 test cases pass against the new candidate. Swapped
in; round 3's candidate is not kept.

## Round 5 (`D100`/`D102`): dependency signatures and synthetic-fixture frontmatter

Two further gaps, both found via `provenance-tracker`'s and (once
regeneration reached it) `spec-bundle-assembler`'s own real test
authorings, fixed together in one round since both are additive,
always-included prompt sections with no interaction: `R-AUTHOR-011`
(`D100`) adds each dependency's own documented `interface/` content
(`CriterionBundle.dependency_interfaces`, mirroring `generator`'s own
field) with an instruction to match any fake against it exactly, since
`provenance-tracker`'s authored tests guessed wrong about two different
dependencies' real call signatures and return shapes despite both
being fully documented. `R-AUTHOR-012` (`D102`) adds the required
`component.md` frontmatter schema (`id`/`title`/`status`/`owners`
always, `realizes` unless sealed) for any synthetic fixture a test
constructs from scratch, since six of `spec-bundle-assembler`'s own
real test authorings built a fixture missing required fields,
crashing several layers down (`graph-query-engine`'s `nodes` view)
instead of failing a clean lint check.

One real `generate()` call produced a candidate correctly implementing
both as separate, clearly-labeled prompt sections. **Verified via
`gen_test_author_v2.py` (generate-only) plus the hand-maintained suite
directly — never `bootstrap_component.py`'s own staged driver**: that
driver's `verify()` step would recursively invoke `test-author` on its
own criteria, since none of them have ever had a
`verification/test-author/generated-test/` file (`D58`'s mocked-backend
exception has always covered 100% of this component's own criteria).
Running it anyway was tried and aborted immediately once recognized;
noted here so a future round doesn't repeat it. `conftest.py`'s
`fake_bundle_dict` gained a `dependency_interfaces: {}` default; 13 of
14 test cases pass directly (the 14th, `AC-AUTHOR-002`, depends on
`spec-bundle-assembler`'s own regeneration adding the same field to
the real `CriterionBundle`, landed separately). Swapped in (written
directly, this component's own established exception to the staged
pattern); round 4's candidate is not kept.

## Round 6 (`D103`): sidestepping realizes/capability-linkage entirely

`spec-bundle-assembler`'s own retry against round 5's candidate got
further, but surfaced the next layer of the same underlying problem:
a synthetic fixture now had the right frontmatter fields present, but
an empty `realizes: []` list, which `spec-linter`'s `R-LINT-006`
correctly rejects. Enumerating individual `spec-linter` rules one real
failure at a time was already showing diminishing returns after two
rounds of this. Fixed by amending `R-AUTHOR-012` in place (`D103`): a
synthetic fixture now defaults to `sealed: true` with a fake
`source_path`, sidestepping `realizes`/capability-linkage (and every
`spec-linter` rule about it) entirely, unless the criterion under test
specifically concerns that behavior. One real `generate()` call
produced a candidate correctly stating this as a conditional default.
Verified via `gen_test_author_v2.py` plus the hand-maintained suite
directly, same as round 5. `TestFile`/`TestAuthoringResult.file` is
now a dataclass again (this round's own representation choice, not
itself required) — the suite's attribute-vs-dict assertions were
updated accordingly. 13 of 14 cases pass directly (the 14th,
`AC-AUTHOR-002`, again depends on `spec-bundle-assembler`'s own
regeneration). Swapped in; round 5's candidate is not kept.

## Round 7 (`D104`, plus `D102`/`D103` split into R-AUTHOR-012–015)

`spec-bundle-assembler`'s retry against round 6's candidate (`D103`'s
`sealed: true` default) got no further than before — but this time, a
thorough diagnosis (hand-patching only the suspect line in each
failing test, in an isolated sandbox, never committed, then re-running
against the unmodified candidate) found the real root cause rather
than guessing again: five of seven still-failing criteria used YAML
**block style** for a frontmatter list field (`owners:\n  - x`), which
this corpus's hand-authored frontmatter reader does not recognize as a
list at all — every real spec file in this corpus uses flow style
(`owners: [x]`) exclusively, confirmed corpus-wide. Patching just that
one line per fixture made all five pass cleanly, proving the
candidate was correct all along. A separate, unrelated bug in this
same investigation (`bootstrap_component.py`'s own sandbox symlinked
`specs/`/`gen/<dep>/` from the real repo rather than copying them; a
test that resolved its own "repo root" by walking up from a loaded
module's `__file__`, not pytest's `tmp_path`, leaked a fixture through
that symlink into the real, committed `specs/components/` tree) had
been the actual cause of an apparent regression one round earlier —
fixed by switching the driver to real copies, and the leaked,
untracked file was removed with no other consequence.

Per the standing `D36`/`D104` practice (diagnose the real cause, add a
structural safeguard, scrub for other instances — not just resolve the
one failure in front of you), this round's fix is two-part, not one:
`R-AUTHOR-014` states flow-style lists explicitly; `R-AUTHOR-015` adds
a standing self-check (lint the constructed fixture first, assert
clean, before testing the real behavior under test) so the *next*
instance of "the fixture itself is invalid," whatever its specific
cause, surfaces immediately and legibly rather than as a confusing
failure several layers downstream. `R-AUTHOR-012` (required fields,
`D102`) and `R-AUTHOR-013` (sealed default, `D103`) were split out of
what had been one accreting requirement, to stay under `R-LINT-023`'s
per-file word cap. A corpus-wide scrub for already-committed instances
of block-style frontmatter lists, in both `verification/` and
`specs/`, found none.

One real `generate()` call produced a candidate correctly stating all
four requirements (`012`–`015`) as distinct, clearly-worded prompt
sections; `PROMPT_VERSION` → `v5`; `GATE_VERSION` is now computed as
`f"{GATE_TYPE}@{PROMPT_VERSION}"` rather than a separate fixed
constant (this round's own reasonable choice). `file`/`model_call_error`
are plain dicts again this round; the hand-maintained suite's
attribute-vs-dict assertions were updated accordingly, and
`AC-AUTHOR-012` was split into four cases matching the four
requirements, with two new cases (`AC-AUTHOR-014`/`015`) added. 16 of
17 cases pass directly (the 17th, `AC-AUTHOR-002`, again depends on
`spec-bundle-assembler`'s own regeneration). Swapped in; round 6's
candidate is not kept.

## Round 8 (`D105`)

`R-AUTHOR-015`'s self-check safeguard (round 7) worked exactly as
designed on the very next real retry: `AC-ASSEMBLE-010`'s fixture
failed with a full, structured finding list instead of a confusing
downstream error, naming three further gaps at once — `status:
active`/`accepted` (the exact mistake `D102` first found, recurring
independently on two different components in two separate real
regenerations, since `R-AUTHOR-012` required `status` be present but
never stated which values are valid), a synthetic decision file
missing `owners` (the universal frontmatter rule had only ever named
`component.md` concretely), and two requirements with zero covering
acceptance criteria. Closed by amending `R-AUTHOR-012` with the
literal `status` enum, naming `VAR-*.md`/`D<N>.md` alongside
`component.md`, and an acceptance-coverage requirement. `component.md`
itself needed trimming afterward to stay under `R-LINT-012`'s
corpus-wide word cap, grown large from eight real rounds' worth of
changelog entries.

One real `generate()` call produced a candidate correctly stating all
three additions; `GATE_VERSION` is a fixed constant again this round
(`generated_test@1.0.0`), `PROMPT_VERSION` reset to `v1` (this
round's own internal versioning choice — the cache key still
correctly distinguishes prompt content via `_gate_inputs_hash`
regardless). One existing assertion (`AC-AUTHOR-010`) needed loosening
for legitimate wording drift ("statically import" vs "statically
importable") — not a regression, the same category of harmless
variance every round has shown. 17 of 18 cases pass directly (the
18th, `AC-AUTHOR-002`, again depends on `spec-bundle-assembler`'s own
regeneration). Swapped in; round 7's candidate is not kept.

This was planned as the last round specifically for the gaps
`AC-ASSEMBLE-003`/`010` surfaced (`D105`'s own context) — whatever
`spec-bundle-assembler`'s next real retry shows, it is landed as-is,
with any remaining gap documented rather than chased further.

## Round 9 (`D106`)

The first real `spec-bundle-assembler` retry against round 8's
candidate did not reach a clean pass/fail at all — it crashed the
whole bootstrap with an uncaught `AttributeError:
'CriterionBundle' object has no attribute 'dependency_interfaces'`.
Traced to a second, independent `CriterionBundle` producer:
`verifier-orchestrator`'s own `_build_criterion_bundle()`, used
whenever `verify()` authors a test against a component's *own*
criteria (every real bootstrap run), predates `R-AUTHOR-011`/`D100`
and never carried `dependency_interfaces` at all — a different
producer from `spec-bundle-assembler.assemble_criterion()`, the one
`D100` actually fixed. `author_test`'s own `_field()` helper did
`getattr(bundle, name)` with no default, crashing on any bundle
missing any field. Closed by `R-AUTHOR-016`: every bundle field
access MUST tolerate a missing field. `verifier-orchestrator`'s own
gap was deliberately left open, tracked as a known limitation, not
fixed here (see Round 12 below — it became load-bearing, not just
theoretical). 17 of 18 cases pass directly. Swapped in.

## Round 10 (`D107`)

With Round 9's crash fixed, the next retry produced a clean result
for the first time but regressed to 8/14 real criteria. Diagnosis: 5
of 6 failures shared one exact cause, confirmed by linting each
failing criterion's own synthetic fixture directly — `status:
ratified` without the `last_ratified_commit` field `R-LINT-002`
requires alongside it. Closed by amending `R-AUTHOR-012` again. The
sixth failure (`AC-ASSEMBLE-007`) was not a bug: `component_context`'s
own interface doc documents its `purpose` column as "verbatim," and
its regex naturally includes a trailing newline the AC's Gherkin
didn't anticipate — a pre-existing-pattern limitation, not chased.
18 of 18 cases pass directly (all of `AC-AUTHOR-012`–`018`, including
two — `017`/`018` — that had specs but no hand-maintained test until
this round). Swapped in.

## Round 11 (`D108`)

The next retry failed all 14 criteria identically with a generic
backend error, `backend call failed (exit code 1)`, reproduced twice.
Diagnosis: `author_test` called `llm_endpoint.complete(prompt, model,
backend=llm_backend, seed=seed)`. `complete()` forwards every kwarg
verbatim into a CLI flag (`R-ENDPOINT-001`, by design); `--seed` isn't
a flag the real backend CLI recognizes, so every real call failed —
invisible under the hand-maintained suite's permissive `MockBackend`,
which silently accepted any kwarg. `generator`'s own call passes only
`prompt`/`model`/`backend` — confirmed as the pattern to match.
Closed by `R-AUTHOR-019`. 21 of 21 cases pass directly (`AC-AUTHOR-002`
passes for the first time, now that `spec-bundle-assembler` is itself
cold-generated with `dependency_interfaces`). Swapped in.

## Round 12 (`D110`)

Before patching the next real failure (`provenance-tracker`'s
`AC-TRACK-010` fake hedged one function under five plausible real
names and still got the arity wrong — the same bug class `D100`
closed once already), this session paused and ran four parallel
agents to pressure-test the whole design rather than add an eleventh
one-off instruction. All four converged: the ~10 real bugs found
across Rounds 1–11 split into two populations, not ten
independent surprises — context genuinely missing from the prompt
(fixable by instructions, Rounds 1–8ish) and `author_test`'s own code
bugs invisible under a too-permissive mock (`D106`, `D108` — not
fixable by prompt engineering at all). Asking the model to self-check
its own fake (`R-AUTHOR-015`) is necessary but not sufficient — a
model that doesn't reliably know a dependency's real signature can't
reliably judge its own guess against it, which the five-alias hedge
itself proves.

Closed by `R-AUTHOR-020`: `author_test` now statically validates its
own output — `ast.parse()`s the content (`malformed_code` on
failure) and best-effort checks any fake-dependency callable's arity
against its real documented signature from `dependency_interfaces`
(`fake_signature_mismatch` on a mismatch) — both in code, never left
to the model. `R-AUTHOR-015` is now a MUST, not a SHOULD. The
hand-maintained `MockBackend` was also hardened directly (not a spec
change) to reject any unexpected kwarg, closing the specific blind
spot that let `D108` through invisibly. 24 of 24 cases pass directly,
including three new tests for `AC-AUTHOR-020` itself (malformed code,
wrong-arity fake, matching-arity fake). Swapped in.

Two further structural gaps were found during the four-agent review
and deliberately **not** fixed here, tracked as known limitations: a
third, field-incompatible `CriterionBundle` producer in
`capability-scenario-verifier` (silent, total content loss if any
capability scenario is ever marked `kind: generated-test` — currently
latent, none are), and `dependency_interfaces` never resolving a type
referenced by a dependency's own signature but owned by a different,
undeclared component (why `provenance-tracker`'s own
`write_attempt_record` call is still underspecified for
`GenerationResult`/`VerificationReport` — tracked for `provenance-
tracker`'s own bootstrap to address or document, not test-author's).

## Round 13 (`D112`)

`provenance-tracker`'s own `R-TRACK-011` fix (`D111`, dependency
loading made `repo_root`-relative) was confirmed working directly in
the candidate's code on the very next retry — but three other criteria
(`AC-TRACK-007`/`009`/`010`) newly failed with
`AttributeError: 'dict' object has no attribute '...'`. Diagnosis:
`write_attempt_record`/`check_readiness` return plain dicts this
round (an undocumented-either-way shape, per this corpus's duck-typing
convention), and in the very same generation batch `AC-TRACK-004`'s
test used a dual dict-or-attribute access helper and passed, while
`AC-TRACK-007`/`009`/`010`'s tests used bare attribute access and
crashed — the model already knew the right pattern and simply didn't
apply it everywhere. Closed by `R-AUTHOR-021`: dual access is now
required for reading the target's *own* return value too, not only a
faked dependency's.

`AC-TRACK-011`'s own generated test failed separately, for a reason
confirmed not to implicate the candidate: a maximally-permissive
"chameleon" fake (`__getattr__` returning `True` for any unmatched
name) made a real precondition check look like a spurious failure.
Not a test-author gap — `AC-TRACK-011`'s own Gherkin was tightened
instead, to require the fake match the real documented signature
rather than invent a duck-typed stand-in.

25 of 25 cases pass directly, including a new test for `AC-AUTHOR-021`
itself. Swapped in.

## Round 14 (`D113`)

A fresh `provenance-tracker` retry (new seed, forcing fresh
test-authoring) surfaced three more real issues in one batch:
`AC-TRACK-010` crashed at runtime with a wrong-arity `TypeError` that
`R-AUTHOR-020`'s own arity check should have caught but didn't — the
fake was written inside a triple-quoted string literal passed to
`path.write_text(...)` (the normal way to write a fake module file),
invisible to an AST walk that only inspected top-level code.
`AC-TRACK-009`/`011` both crashed on a fake `impact-analyzer`
returning a bare list instead of the documented `BlastRadiusReport`
object — the identical mistake `R-AUTHOR-011`/`D100` was created to
close, recurring twice more despite the real, field-documented shape
being present in `dependency_interfaces` the whole time. A third
failure (`comp-provenance-tracker is documented to declare no
dependencies at all`) traced to genuinely ambiguous wording in this
session's own `AC-TRACK-004` Gherkin, not a test-author gap — fixed
directly, no `R-AUTHOR-*` change needed.

Closed by amending `R-AUTHOR-020` (the arity check now also parses
any string literal that itself parses as valid Python, not only
top-level code) and `R-AUTHOR-011` (added one worked example:
a fake MUST expose every field of a documented return type, never a
bare list/string/number, even if the test reads only one field).

26 of 26 cases pass directly, including a new test confirming the
arity check now catches a wrong-arity fake hidden inside a string
literal. One hand-maintained assertion (`AC-AUTHOR-006`) needed
loosening to accept either an absolute or a `repo_root`-relative
`file.path` — confirmed `verifier-orchestrator` itself already
tolerates both (it joins only when not already absolute), so this
was this session's own test being stricter than the real contract,
not a regression. Swapped in.

## Round 15 (`D115`)

A `spec-bundle-assembler` retry exercising `D114`'s new
`R-ASSEMBLE-013` (transitive type resolution) passed that new
criterion directly, but regressed on three previously-passing ones,
all for one cause: synthetic fixtures gave `constraints.md` a
frontmatter block, which `R-LINT-016` correctly rejects — unit files
carry none at all, only `component.md` does. `R-AUTHOR-012`'s
"these fields are required" instruction had evidently over-applied
to a file class it never meant to cover. Closed by stating the
opposite rule in `R-AUTHOR-012` just as explicitly. 26 of 26 cases
pass directly. Swapped in.

## Round 16 (`D116`/`D117`)

Diagnosed `spec-linter`'s own `interface/library.md` as understating
`lint()`'s real signature (missing `| None` on `paths`, missing
`judge` entirely) — a pre-existing documentation gap, fixed directly
with no regeneration needed since `spec-linter`'s code was already
correct. The next retry improved concretely (two previously-failing
criteria now called `lint()` correctly) but three others still wrote
`lint(repo_root)` — one positional argument — despite the corrected
signature now being in the prompt as prose. Closed by `R-AUTHOR-015`
now including the exact call as a literal worked snippet,
`lint(None, repo_root)`, the same "prose alone isn't reliably
sufficient" lesson `R-AUTHOR-010`/`011` already learned for their own
conventions. 26 of 26 cases pass directly. Swapped in.

## Round 17 (`D119`–`D123`)

`verifier-orchestrator`'s own missing `dependency_interfaces` (`D119`,
`D120`) was the real, deeper root cause behind every dependency-
shape-guessing failure this whole investigation ever hit — once
fixed, `provenance-tracker` jumped from 3/6 to 6/7 across several
retries, each surfacing one real remaining issue in turn:
dual access reading a dependency's own return value (`D121`), the
`realizes` edge computed the wrong direction entirely (`D122`), and
finally — recurring at two different seeds with the identical
symptom — a generated test asserting fake usage via a guessed
`sys.modules["real_name"]` key instead of the fake's own already-
recorded call list (`D123`). Closed by `R-AUTHOR-022`: never assert
via a guessed `sys.modules` key: rely on the fake's own recorded
invocation instead. 27 of 27 cases pass directly, including a new
test for `AC-AUTHOR-022`. Swapped in.

## Round 18–19 (`D125`, `D126`)

With `verifier-orchestrator`'s mutation-score fix landed (`D124`),
`provenance-tracker` reached `mutation_score=1.0` directly, surfacing
two more real, isolated bugs: a recurring wrong function name
(`run_capability_scenarios` instead of `run_capability_gates`, closed
with a literal worked call in `R-TRACK-010`) and a generated test
`import yaml`-ing — the identical `D101` lesson, generalized to
test-authoring itself (`R-AUTHOR-012`, `D125`).

Regenerating against the `D125` amendment surfaced a real regression
of its own: `R-AUTHOR-020`'s arity check detected `name = other_name`
aliases correctly but then explicitly skipped every one of them when
comparing arities, never resolving an alias to its target function's
own real arity — so the one name a real dependency signature actually
names (the alias) was never checked at all. Confirmed directly
against the hand-maintained suite's own `AC-AUTHOR-020` wrong-arity
test, which failed cleanly once this was caught. Closed by `D126`:
aliases MUST resolve to their target's own arity, never skipped.

Along the way, this session's own hand-maintained suite needed
hardening too: `author_test`'s own top-level return value is itself
duck-typed (`D94`) — a dict in this round, a dataclass in others —
and the suite had assumed attribute access throughout. Generalized
the existing `_file_field` pattern into `_rf()` for the whole
`TestAuthoringResult`, and loosened three more assertions for
legitimate wording drift (`statically import` phrasing,
`hyphens`/`underscores` phrasing, the dependency-path placeholder
convention) — none of these were regressions, each confirmed by
inspecting the real rendered prompt directly before loosening.
27 of 27 cases pass directly. Swapped in.

## Round 20 (`D129`): write-time window truncation

First real cold-generation attempt for `provenance-writer` surfaced a
genuine test-authoring gap in a shape this corpus hadn't exercised
before: a wall-clock "own write time" field documented at whole-second
precision (`generated_at`, ISO `%Y-%m-%dT%H:%M:%SZ`). The generated
test (`AC-PROV-008`) captured its own `before`/`after` window bounds at
full microsecond precision via plain `datetime.now(timezone.utc)`,
then compared the truncated-to-the-second written value directly
against them — a correctly implemented candidate fails this on almost
every real run, since truncating down to the start of a second makes
the written value numerically less than `before` whenever `before`'s
own microseconds are nonzero. New `R-AUTHOR-023`: the prompt MUST
instruct truncating `before`/`after` to the field's own documented
precision before comparing. Regenerated directly against the real
`REPO_ROOT` (`D58` bootstrap exception, same as every other round):
28 of 28 hand-maintained cases pass, including a new
`test_ac_author_023_...` proving the instruction is actually present
in the rendered prompt — confirmed failing against the prior round's
candidate first. Swapped in (this component's generate-only path
already writes directly to the live repo as a side effect).

Blast radius checked (`D99`): `capability-scenario-verifier` (4/4) and
`verifier-orchestrator` (15/15) are the only already-built dependents;
both pass unchanged. `component-gate-runner` is also a dependent but
not yet built.

Round 21 (`D143`, superseded by `D144` below): bootstrapping
`review-packet-builder` hit the identical failure shape on two
independent criteria across different seeds — a generated test's
fake correctly recorded its own invocation (per `R-AUTHOR-022`), but
the test asserted against a stale, pre-call local reference to its
own separate load of the fake module, never noticing the candidate's
own loader (correctly, per `R-GEN-018`) `exec_module`s a fresh module
object every call, replacing `sys.modules` and orphaning that earlier
reference. `R-AUTHOR-024` first instructed reading the recorded
invocation back through `sys.modules[module_name]` *after* the call
under test returns, regenerated and swapped in, 28/28 hand cases
passing — but this instruction itself guessed a bare `sys.modules`
key, the exact failure `R-AUTHOR-022` already forbids; see round 22.

Round 22 (`D144`): the very next `review-packet-builder` retry against
round 21's fix regressed severely, 9 of 11 failing — every new fake's
test read `sys.modules["provenance_tracker"]` (the bare name) after
the call, but that round's real candidate keyed its loaded module
under a unique, `repo_root`-qualified name instead
(`_hotdocs_dep_<slug>_<module_name>_<id(repo_root)>`), exactly the
dynamic keying `R-AUTHOR-022`/`R-GEN-018` already warn a test can
never predict. `R-AUTHOR-024` rewritten (not superseded — never
shipped anywhere else): confirming a fake's invocation MUST use a
file-based log the test controls, never any in-process `sys.modules`
lookup at all; `R-AUTHOR-022` cross-amended to the same effect.
Regenerated again: 29 of 29 hand-maintained cases pass (one pre-
existing phrasing-variance test, `AC-AUTHOR-010`, needed its own
accepted-phrasing list widened — unrelated to this fix, just newly
exposed by a different real wording this round). New
`test_ac_author_024_prompt_states_file_based_invocation_log`
confirmed to fail against the pre-`D143` baseline (missing
"in-process"/"in process" wording) when loaded by explicit file path,
bypassing `conftest.py`'s own `sys.path` precedence for the real
installed module. Swapped in (generate-only path writes directly to
the live repo). Blast radius re-checked: `capability-scenario-verifier`
(4/4) and `verifier-orchestrator` (15/15) still pass unchanged.

## `D166`: a fake's name shared by two dependencies

`component-gate-runner`'s first round failed 11 of 13 criteria with
`fake_signature_mismatch: scan` before any test ran. Its dependencies
`license-scanner` (`scan(component_id, repo_root)`) and
`secret-scanner` (`scan(repo_root)`) share a function name, and the
fake-arity check keyed signatures by bare name, so one dependency's
arity silently replaced the other's. `R-AUTHOR-020` already said to
skip what is ambiguous; it now says a shared name matches if the fake
fits any of the dependencies' arities.

Regenerated directly per the `D58` exception. The first candidate was
served twice from `generator`'s cache, since the spec had not changed
between attempts; a third, informed by `--retry-feedback`, passed the
new behavior. Three of its apparent failures were defects in this
directory's own hand tests, fixed here: two checks required the plural
words "hyphens" and "underscores" where a correct prompt said "every
hyphen replaced by an underscore", and the new collision test reused
one `repo_root` for three cases, so the last two were served from
`test-author`'s cache instead of being validated. 32 of 32 pass;
`verifier-orchestrator` and `capability-scenario-verifier` suites
unchanged.
