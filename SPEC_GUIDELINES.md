# Spec Guidelines

This document is the rulebook. Every authoring agent, generation agent, and
linter invocation in this repository follows it. It states **what** is
required; it does not re-derive **why** — the rationale and the decision
history live in `notes/initial-ideas.md` (`D1`–`D14`, informal brainstorm,
its own frozen historical numbering) and `specs/decisions/` (the formal
ADRs — `D1`–`D75` renumbered at the 2026-10 baseline reset, `D76` onward
recorded as made; what a bare `D<N>` citation means is in
`specs/architecture/glossary-and-citations.md`, `D381`) and are cited here
by number for traceability, not repeated.

The rules a component checks mechanically live in five
`specs/architecture/` documents, each named where its rules used to be
below (`D381`): `spec-layout.md`, `spec-frontmatter.md`,
`acceptance-criteria.md`, `size-caps.md` and `glossary-and-citations.md`.

Keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
used per RFC 2119. This document is itself a spec of the methodology, so it
follows its own rule: no open questions, no ambiguity a linter couldn't catch.

---

## 1. Repository layout

```
specs/                 # the specs — tree in specs/architecture/spec-layout.md
SPEC_GUIDELINES.md      # this file
gen/                   # generated code
pipeline/              # workflow definitions, frozen prompts, model pins, toggles
verification/          # generated tests, contract checks, corpus-graph.json
tools/                 # hand-written repo-maintenance/authoring scripts —
                       # outside the spec-driven pipeline entirely (not
                       # generated, not gated, never read by any rule in
                       # this document). Scaffolding convenience only.
notes/                 # brainstorming — non-normative, not read by the pipeline
.hotdocs/              # LOCAL ONLY, gitignored — provenance-tracking records
  attempts/            # (provenance-tracker, D19) one record per per-component
                       # generation+verification attempt, full detail —
                       # what D3's retired best-of-k loop used to fold
                       # into one provenance manifest, now the only place
                       # a blocked attempt's detail survives at all
  calls/               # (llm-endpoint, D20) one record per model call,
                       # caller-agnostic, transport-level only
                       # All of the above: never committed, never read by
                       # any gate's pass/fail decision — purely observability.
```

- `specs/` **MUST NOT** contain executable code of any kind, generated or
  hand-written. (D4)
- `gen/` and `verification/` **MUST** be committed on every branch. Large
  generated binary assets **MUST** go through Git LFS rather than a plain blob
  commit. (D6)
- The flat-module-or-package layout rule for a component's code under
  `gen/<slug>/` is in `specs/architecture/acceptance-criteria.md` (`D381`).
  It is load-bearing, not stylistic: `dependency_usage` silently (by
  design, fail-to-empty) returns nothing for a dependency it can't find
  there — found only once a real generated candidate chose a `src/`
  layout instead (`D46`).
- Nothing under `gen/` or `verification/` is hand-edited, with exactly two
  declared exemptions — see §8.
- `.hotdocs/` **MUST** be gitignored and **MUST NOT** be read by any gate's
  pass/fail decision — it is observability data about past `hotdocs generate`
  attempts, never an input to any check. This is a correctness boundary, not
  just a storage convention: letting a gate's decision depend on local,
  uncommitted history would break every determinism/purity requirement
  elsewhere in this document (e.g. `impact-analyzer`'s R-IMPACT-006).
- `tools/` is committed (unlike `.hotdocs/`) but otherwise occupies the
  same "outside the methodology" position: a script here **MUST NOT** be
  invoked by any gate, and **MUST NOT** write to
  `specs/`/`gen/`/`verification/` on a human's behalf without the human
  reviewing the result before committing — it may *create* new, empty
  scaffolding (directory structure, placeholder frontmatter), never
  author normative content. The distinction that matters: a scaffolding
  script removes mechanical friction; it does not do the spec-authoring
  work D1 reserves for a human or an assist agent.
- The governed set of spec files, and the `README.md` skip, are in
  `specs/architecture/spec-layout.md` (`D381`). (Found while bootstrapping
  `spec-linter` — nothing previously said how to tell a real spec from a
  placeholder sitting in the same directory.)
- **Why one file per unit, not one file per document type (`D1`).** A
  component's individually-addressed units — each requirement, each
  acceptance criterion, each interface section — get their own file;
  narrative/frontmatter does not. This replaced an earlier four-flat-files
  design (`spec.md` / `interface.md` / `acceptance.md` / `constraints.md`)
  once it became clear
  the flat-file version was both harder to hash precisely for blast-radius
  purposes (D2's "interface change vs. internal change" distinction needed
  section-level parsing to approximate) and inconsistent with itself (every
  `R-id` and every `AC-id` was already independently addressed by other
  specs — `realizes`, `uses_var`, `Covers:` — while living in a shared file
  with no file-level boundary to hash against). One file per unit makes
  content hashing *exact* rather than approximated, and removes a whole
  class of block-boundary parsing bugs (the kind that caused a real,
  caught-in-testing bug in `spec-linter`'s own bootstrap).

---

## 2. Universal frontmatter

The frontmatter rules — where frontmatter lives, the field table, and
the rules over it — are in `specs/architecture/spec-frontmatter.md`
(`D381`).

Frontmatter lives only in a component's `component.md`, never in its
unit files. This replaced an earlier, less uniform rule — "only
`spec.md` carries the full field set, the other three carry
`id`/`title`/`status`/`owners`" — once the component was split into
one-file-per-unit: there's no longer a meaningful "this sub-file's own
id/status" to track separately from the root's. The ban on unit-file
frontmatter used to rely on that convention; it now holds by
construction.

---

## 3. Document types

### 3.1 Product capability (`specs/product/<name>.md`)

Its rules are in `specs/architecture/spec-layout.md` (`D381`).

### 3.2 Architecture (`specs/architecture/<name>.md`)

The only place the component decomposition itself is declared and changed.
Splitting or merging components is **not** a normal spec change — it **MUST**
go through this area, as its own reviewed operation, distinct from an ordinary
component spec edit. (D2)

### 3.3 Var declaration (`specs/vars/<name>.md`)

Its fields and rules are in `specs/architecture/spec-frontmatter.md`
(`D381`).

### 3.4 Component (`specs/components/<name>/`)

A component's files, `component.md`'s section order and the rules for
requirements, interfaces, acceptance files and `constraints.md` are in
`specs/architecture/spec-layout.md` (`D381`).

A spec is not "done" until an authoring/generation agent can execute it
with zero clarifying questions.

`Purpose` is the one section a *dependent* may see as part of its own
context (`notes/backlog.md`'s "context" idea, once built); Rationale
holds everything Purpose used to carry that isn't dependent-safe. D2
extended "the contract" to include behavioral guarantees, not just type
signatures.

When a dependent needs one more fact than an existing boundary like
this one currently exposes, see `notes/narrow-exception-pattern.md` —
the move is almost always a new, narrowly-named field or mechanism
alongside the original, never a loosened definition of what the
original already means.

`constraints.md` is deliberately **not** split like the three unit
directories: nothing elsewhere in the corpus addresses one individual
constraint by id the way `Covers:`/`realizes`/`uses_var` address a
requirement, criterion, or interface section — there's no
reference-granularity reason to pay the extra-file cost here.

### 3.5 Decision record (`specs/decisions/<id>.md`)

Its rules are in `specs/architecture/glossary-and-citations.md`
(`D381`). See `specs/decisions/README.md` for the full guidelines —
frontmatter shape, `supersedes`/`builds_on` semantics, citation
discipline, and the grep-based drift check.

### 3.6 Glossary (`specs/glossary.md`)

The glossary's rules, its entry format and how an entry is cited are in
`specs/architecture/glossary-and-citations.md` (`D381`).

**When to promote a fact here** (the judgment call §4's component-sizing
trigger makes for size, made explicit for shared vocabulary): a
convention, naming formula, file-path pattern, or callable contract
**MUST** be promoted to the glossary as soon as a second component's
spec states it, relies on it, or would need to independently guess it
— never left to live only in one component's own text (where a
dependent's `SpecBundle` never sees it, `R-ASSEMBLE-002`) or only in
real `gen/` code (where no spec ever sees it at all). §10's "single
source of truth for computed facts" is the sibling discipline for
*calculations*; this is the same discipline for *shared vocabulary and
contracts* — a convention is not "computed," but it is exactly as
unsafe to let two components independently reinvent.

  Before writing a requirement that describes how your component uses
  or constructs a fact belonging to *another* component's contract —
  not your own component's purely internal behavior — check whether
  `glossary.md` already names it. If it doesn't, and a second real
  consumer now exists (this requirement, plus whichever component you
  found the convention in originally), promote it there as part of the
  same change, not as a follow-up. See `notes/audit-before-you-build.md`
  for the analogous habit already established for *data that already
  exists but isn't yet being read*; this is the same habit for
  *conventions that already exist but aren't yet written down*.

  The citation check catches citation drift (a renamed or removed term,
  a typo) once a term is cited; it cannot detect a fact that should
  have been promoted but wasn't — that half stays a judgment call,
  which is why this paragraph, not a linter rule alone, is the actual
  fix.

---

## 4. Component sizing

The split trigger, the size caps, how each dimension is measured, and
the decomposition-signal rule are in `specs/architecture/size-caps.md`
(`D381`). Its caps table (`D380` replaced the component-docs word cap
with the two bundle caps):

| Dimension | Warn above | Hard fail above |
| --- | --- | --- |
| Generated code per component | 800 LOC | 1500 LOC |
| Generator bundle words (`generator_words`) | 8000 | 14000 |
| Largest criterion bundle words (`criterion_words_max`) | 6000 | 12000 |
| Requirements per component | 20 | 40 |
| Public interface surface elements | 10 | 20 |
| `depends_on` count (fan-out) | 7 | — (warn only) |
| Dependents count (fan-in) | 10 | — (warn only) |
| Guarantees per component | 5 | 10 |
| Acceptance criteria per component | 25 | 50 |
| Per-file words (`requirements/`, `acceptance/`) | 250 | 500 |
| `Purpose` section words | 80 | 150 |

The guarantee, acceptance-criteria and per-file caps are a first pass
(D17), calibrated against this corpus's own content at the time they
were added rather than an a priori judgment — expect them to be
revisited as more components exercise them. `guarantee_count` in
particular had no cap at all before: the interface-surface-elements row
deliberately excludes `interface/guarantees/` (a promise, not a
callable surface element), which meant an unbounded number of guarantee
files could previously accumulate with zero signal.

**A decomposition signal, not just a cap to satisfy.** A single dimension
running high can be an accepted shape on its own — a thin coordinator
legitimately has wide fan-out with little owned logic of its own (see
`specs/architecture/pipeline-decomposition.md`'s note on
`merge-orchestrator`). But when **two or more independent dimensions**
crowd their ceilings **for the same component at the same time**,
treat that as a sign the component owns a cross-cutting concern that has
outgrown its placement, not as evidence the caps themselves are
miscalibrated.
Two shapes of this have shown up in practice so far, not just one: a thin
coordinator crowding fan-out together with component-doc words
(`merge-orchestrator`, resolved by `D14`), and a self-contained component
with no fan-out at all crowding component-doc words together with its own
requirement/acceptance/generated-code counts instead (`spec-linter`
itself, after `D17` added those dimensions — fan-out is irrelevant there;
the signal is still real). (Component-doc words was the dimension `D380`
replaced with the two bundle caps.) Fan-out measures how many neighbors a
component calls; the count/words dimensions measure how much it owns
directly. A thin coordinator runs fan-out high without the others; a
dense, isolated component can crowd several of the others with zero
fan-out. Either combination means the component isn't just one simple
shape (thin-and-wide, or fat-but-isolated) — it's carrying more than one
dimension's worth of cost at once.

The fix is not automatically a bigger cap, but it is also not
automatically a split — the signal means "look closely," not "extract
something." Start by asking whether a structural precedent for a split
already exists elsewhere in the corpus: `D14` extracted
`capability-scenario-verifier` out of `merge-orchestrator` once both caps
crowded at once, because that logic was already the cross-component
analog of `verifier-orchestrator`'s existing per-component dispatch — the
split mirrored a pattern already present, it wasn't invented from
scratch. The dimension that should actually move is component-doc
words — but don't assume fan-out's own fate either way without
checking: `D14`'s extraction left it flat (`merge-orchestrator` had its
own independent reasons to keep calling several of
`capability-scenario-verifier`'s own dependencies directly), while
`D76` — the same kind of extraction, applied to `merge-orchestrator` a
second time, for `component-gate-runner` — saw it actually drop (every
dependency the new component encapsulated had no other caller). Whether
fan-out drops depends on whether the coordinator had a second reason to
call the extracted dependencies directly, not on the extraction pattern
itself. See `notes/component-sizing-playbook.md` for both worked
cases.

Sometimes the honest conclusion is that no precedent exists and no split
is warranted: `spec-linter` crowding `generated_code_loc`,
`requirement_count`, and `component_doc_words` together (`D77`) reflects
one cohesive component with many genuinely independent, correlated rules —
not a hidden second responsibility with some other component's shape to
borrow. Splitting a single-pass structural linter into sub-checkers for
no architectural reason would be the wrong response to this signal, not
the right one; treat the signal as a prompt to check for a real
precedent, not a mandate to always act on it. If fan-out was the *only*
dimension crowding, that's a different, already-accepted case —
D2's "thin coordinator" shape, not this signal at all.

See `notes/component-sizing-playbook.md` for the worked decision
procedure and tightening toolbox this principle compresses — a
step-by-step guide grounded in this corpus's own real cases (`D14`,
`D17`, `D29`), not abstract advice.

---

## 5. Acceptance criteria

The format of acceptance criteria and capability scenarios, the three
`kind`s and every rule over them are in
`specs/architecture/acceptance-criteria.md` (`D381`).

A documented CLI with no requirement pinning its argument parsing is
untested code that mutation testing will find anyway, one survivor at a
time. See `notes/determinism-trust-playbook.md` for how the `kind` split
drives caching/trust design elsewhere in the pipeline (only `llm-judge`
is ever a genuine trust decision; `compiled`/`generated-test` are
always cheaply re-derivable), and `notes/structured-judgment-output.md`
for the `{result, rationale}` pattern the `llm-judge` rationale rule is
one instance of.

---

## 6. Verification gates

**No component automates this sequence end to end (`D87`).** A developer
drives it directly:

1. **Spec lint** — structure, frontmatter, RFC 2119 usage, no open questions in
   ratified specs, glossary conformance, acyclic dependency graph, full
   traceability closure (every `R-id`, `realizes`, `uses_var`, `depends_on`,
   `depends_on_guarantees` reference resolves), size caps. Run directly;
   nothing gates `hotdocs generate`/`hotdocs verify` on it, but there is
   no reason to attempt either against a spec that won't lint clean.
2. **`hotdocs generate <component-id> --model=<model-id> [--seed=...]
   [--retry-feedback=...]`** (`component-gate-runner`, `D86`/`D91`/`D93`)
   — one component at a time, run by a developer in `depends_on` order
   across a multi-component change. Checks provenance first (skip real
   work on a hit); on a miss, the pinned model, cold, no prior code,
   from the spec bundle (`component.md` + `requirements/` + `interface/`
   + `constraints.md` + depended-upon components' `interface/` +
   referenced `specs/vars/` declarations + `glossary` — deliberately
   excluding `acceptance/`, so the model doesn't overfit to its own
   tests); per-criterion verification (compiled / generated-test /
   llm-judge, per §5, contract/property tests from `interface/`, the
   interface-drift check); license and secret scans, unconditional
   (D7/D12); provenance written last; the attempt recorded via
   `provenance-tracker`'s `write_attempt_record` regardless of outcome.
   Exactly one generation attempt per call — no automatic retry
   (D1/D3: the best-of-k retry this step used to run was retired).
   `--retry-feedback` (the immediately preceding attempt's failing
   requirements against this same component) MAY be supplied against an
   unchanged spec — this folds into the generation cache key
   (`R-GEN-005`), so it is already a fresh attempt, with no separate
   retry mechanism needed — but only if a human explicitly supplies it
   (D3); nothing computes or injects it automatically.
3. **`hotdocs verify [--changed=...] [--model=<model-id>] [--format=...]`**
   (`provenance-tracker`, `D88`/`D93`) — for every component in scope
   (a single id's blast radius via `impact-analyzer`, or the whole
   corpus), a pure, read-only check against `provenance-checker`; this
   never triggers `component-gate-runner` itself — generating new code
   is `hotdocs generate`'s own deliberate action, never a side effect
   of checking readiness. Then, for every product capability whose
   realizing components are now all current: `capability-scenario-verifier`
   (`D89`) checks its own provenance and, on a miss, runs that
   capability's scenarios against the real, fully assembled `gen/`
   output — not a prediction, the actual regenerated system — then
   writes its own provenance, keyed on the realizing set's actual
   current content (deliberately not their `spec_bundle_hash`es, so an
   undeclared upstream change still invalidates it). Unlike the
   component half, this is check-then-run, not pure read: capability-
   scenario verification never produces new source code, only exercises
   what already exists, so `hotdocs verify` triggering it costs a
   developer nothing they wouldn't expect from a command named
   "verify." `--model` is required only if some capability in scope
   actually needs a fresh run. This is the backstop for cross-component
   behavioral risk that no amount of interface-level diffing can rule
   out in principle (D2) — not a redundant check: `interface/guarantees/`
   (D2) makes *foreseen* behavioral dependencies explicit and
   propagating, this gate catches what wasn't foreseen. `hotdocs
   verify` then reports one ready/not-ready verdict across everything
   it just checked — this is the confirmation a human reads before
   committing; it does not enforce anything itself (`D87`), the same
   posture `.hotdocs/`'s own non-gating rule already states. **Running
   it is nonetheless a stated MUST before any commit of a regenerated
   component** (`D99`) — scoped to the full blast radius of every
   component actually changed (`--changed=<id>...`, letting
   `impact-analyzer` compute the transitive set, never hand-picked),
   not just the one component a developer happened to just regenerate
   in isolation. This is workflow discipline, not a new automated gate
   — no component checks that a developer actually did this before a
   commit lands, the same absence of enforcement `D87` already
   describes — but it is no longer merely optional good practice.
4. **Non-functional gates** where feasible (benchmarks, size budgets).
5. **Review** — `review-packet-builder` assembles the same picture
   `hotdocs verify` checked (spec diff, changed requirements,
   regenerated components, verification results, residual risk,
   license/secret flags, provenance-hit status, capability-scenario
   results, any new/changed `sealed`/override declarations) into a
   static, reviewable artifact, reading `provenance-tracker`'s own
   aggregate (`D90`) rather than recomputing anything. A human reviews
   this and the spec diff. **No human review of generated code is
   required, of any kind.** (D5)
6. **Commit** — only after step 3's blast-radius-wide `hotdocs verify`
   reports `ready: true` (`D99`): `specs/`, `gen/`, and `verification/`
   (including `corpus-graph.json`) update atomically, by the developer,
   in one squashed commit — ordinary version control, not a
   component's own action.

A component whose spec bundle exactly matches an already-verified prior
state **MUST** be treated as a provenance hit (`provenance-checker`,
`D29`) — its committed `.provenance.json` has a matching
`spec_bundle_hash` and `gate_versions` — and `hotdocs generate` restores
the matching artifacts, skipping regeneration and re-verification. The
non-spec-driven-change lane still re-runs asynchronously afterward as an
environment-drift safety net. (D11) This is distinct from
`cache-manager`'s own, narrower per-gate cache (cache key:
`spec_bundle_hash`, `artifact/gate-inputs hash`, `gate_version`,
`model_pin`), which only ever decides whether a model gets called
again, never whether verification is skipped (D13).

A gate's `gate_version` **MUST** bump whenever its underlying detection logic
changes (e.g. the license scanner's signature database), so neither a
cache hit nor a provenance hit ever papers over a genuinely changed risk. (D81)

**Responding to a real defect found through this process is always three
steps, never one** (D36/D104): (1) diagnose the actual root cause —
never accept a surface symptom (a crash, a wrong assertion) as the
explanation; a rejected candidate is never hand-patched, the spec is
fixed and the candidate regenerated through the real pipeline instead
(D36). (2) Fix it in the spec, and add a structural safeguard that
would catch a recurrence of the same class of mistake early and
legibly — not just resolve the one instance found. (3) Scrub the
existing, already-committed corpus for other live instances of the
identical defect, not only the one that happened to surface first.
Skipping straight to "this one test now passes" without the other two
steps is exactly how the same defect reappears later, found the hard
way again.

---

## 7. Provenance

Every generated artifact carries `.provenance.json` alongside it (in
`gen/<component>/` and `verification/<component>/`), committed under the same
discipline as the artifact itself. The manifest is defined by
`specs/components/provenance-writer/interface/data/provenancemanifest.md`
(`D377`); the summary below is for orientation and defers to it:

```
spec_bundle_hash    content hash of every spec file that fed generation
model_pin           model id + version
prompt_version      id of the frozen prompt template used
retry_feedback      R-id list the landing attempt was given (R-GEN-012),
                    null if it was blind
generation          mode (single or agentic), generator_version,
                    transcript_sha256, turns, tool_calls, isolation —
                    hashes and counts only, never a transcript (D312)
attempts            attempts recorded for this component so far
attempt_history     one entry per attempt of the landing run: number,
                    outcome, retry_feedback, error_category,
                    failed_requirements, transcript_sha256 (D310)
pipeline_version    version of the generation pipeline itself
gate_versions       per-gate version map (compiler, license_scanner,
                     mutation_harness, secret_scanner, ...)
provenance_hit      bool — if true, the fields below are copied from the
                     matching prior commit (via provenance-checker,
                     D29), not freshly computed. Renamed from cache_hit,
                     which never actually meant cache-manager had an
                     entry — that's a per-gate concern, e.g.
                     GenerationResult's own cache_hit field.
generated_at
verification_run_id
verification_report  the VerificationReport (verifier-orchestrator)
license_scan        result (license-scanner)
secret_scan         result (secret-scanner) — missing from an earlier draft
                     of this schema even though gate_versions already
                     expected a secret_scanner entry; found while specifying
                     provenance-writer, which is what actually assembles
                     this file from every other component's output
assets              the VerificationReport's assets: per declared asset,
                     kind, path, definition/adapter SHA-256, versions,
                     lockfile_sha256; [] when none (D343)
```

This is the evidence trail for incident debugging (is this a spec bug or a
generation bug?) and doubles as an SBOM/SLSA-style attestation.

A **sealed** component (§8) has no generation to record, so it carries a
different file instead, `.sealed-provenance.json` at its `source_path`
(`D170`). It names the component's `owners`, a hash of the source files
it describes, the verifier version, and the outcome of the
characterization-test run against exactly that source. It is validated
field by field and fails closed: a manifest that is missing, malformed,
for different source, or for different owners is no evidence at all, so
the component is not ready until `hotdocs generate` re-runs its
characterization tests and rewrites it. Its schema is
`provenance-writer`'s `interface/data/SealedProvenance.md`.

Before designing any new mechanism to record or prove a fact happened,
check whether this manifest (or the commit ledger it rides on) already
carries it — see `notes/audit-before-you-build.md`.

---

## 8. Exemptions from cold regen

Exactly two, both declared and tracked — never silent:

**Sealed components** (component granularity). `sealed: true` + `source_path`.
The component's spec says only "matches existing behavior; do not
regenerate." Its code lives at `source_path`, **MUST NOT** be under `gen/`.
Exempt from `realizes` and the cold-regen invariant. **MUST** have
characterization tests in `verification/<component>/` the normal way —
wrapping legacy code in traceability doesn't require rewriting it. Its
ownership and its last verification are recorded in a sealed provenance
manifest at `source_path` (§7).

**Pinned overrides** (file granularity). Declared in
`gen/<component>/.overrides.json` — exempted file paths, rationale, owner.
**MUST** have characterization tests meeting the same bar as a sealed
component. Visible in the review packet and the corpus graph. Used only when
a human-authored override is genuinely needed (e.g. a non-functional hot spot
agents are weak at) — not a general escape from generation.

Nothing else is exempt. Hand-edits to `gen/` outside these two declared
mechanisms are a hard CI failure.

---

## 9. Secrets

Unconditional, not a scope question:

- Secrets **MUST NOT** appear anywhere in `specs/`, `gen/`, or `verification/`.
- An automated secret-pattern scan runs pre-merge-gate and, where tooling
  allows, as early as pre-commit/pre-push.
- Config *contracts* (name, type, required/optional, description) belong in
  `specs/vars/`. Config *values*, and infra-as-code/provisioning, are **out of
  scope** for this methodology — conventionally managed, outside `specs/`.

---

## 10. Single source of truth for computed facts

Any atomic fact more than one component could need — a word count, a
graph relationship, a verification verdict, a provenance field — MUST
have exactly one canonical definition in the corpus. A second
component needing the same fact MUST read or query that definition,
never recompute it independently, however small the computation looks.
This corpus has already been caught by exactly this gap once
(`component_size`, `D13`): two independently-written algorithms for the
same word count, one of them never actually run, silently diverging
from the other it was supposed to match.

- **Before specifying a new computation, check whether it already
  exists** — a shared view (`specs/architecture/graph-query-engine.md`'s
  "Query surface"), an already-written manifest
  (`provenance-writer`'s `.provenance.json`), or another component's
  already-computed result. See `notes/audit-before-you-build.md` for
  the concrete places to check, in order.
- **When a second component needs a fact one component's spec already
  defines, promote the definition to shared, explicit infrastructure**
  rather than let two components each maintain their own copy — the
  same rule that has grown `graph-query-engine.md`'s shared views from
  two to six so far, each time a second real consumer appeared.
- **A requirement that claims a specific implementation mechanism
  (`"implemented as queries over X"`, `"MUST reuse Y's exact
  algorithm"`) is a claim about running code, not a description to take
  on faith.** Verify it actually runs, against real data, before
  treating it as settled — `component_size`'s SQL was wrong in three
  separate ways that reading it never would have caught, only running
  it did. An unverified claim like this is itself a single-source-of-
  truth violation in waiting: the spec describes one mechanism, the
  code silently does another, and nothing but careful reading connects
  the two until something breaks.
- **This is a design-time discipline, not a runtime cache-hit question**
  — don't confuse it with `notes/determinism-trust-playbook.md`'s
  three bands, which classify whether a *result* is safe to reuse
  across calls. This section is about whether a *computation itself*
  has one definition or two.

## 11. What this document does not cover

Implementation details — the actual linter, the generation pipeline's code,
prompt templates, the corpus-graph renderer — live under `pipeline/` and
`verification/` and are not specified here. This document is the contract
those implementations must satisfy, not the implementation itself.
