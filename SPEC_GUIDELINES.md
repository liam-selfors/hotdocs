# Spec Guidelines

This document is the rulebook. Every authoring agent, generation agent, and
linter invocation in this repository follows it. It states **what** is
required; it does not re-derive **why** — the rationale and the decision
history live in `notes/initial-ideas.md` (`D1`–`D14`, informal brainstorm)
and `specs/decisions/` (`D15` onward, formal ADRs) and are cited here by
number for traceability, not repeated.

Keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
used per RFC 2119. This document is itself a spec of the methodology, so it
follows its own rule: no open questions, no ambiguity a linter couldn't catch.

---

## 1. Repository layout

```
specs/
  product/            # capabilities (P-id) + golden end-to-end scenarios
  architecture/        # component decomposition, dependency graph ownership
  vars/                # env/config parameter declarations (VAR-id) — never values
  components/
    <component>/
      component.md      # root: frontmatter + Purpose/Rationale/Scope/
                         # Definitions/Open questions/Change log +
                         # pointers to the below (Rationale optional, D34)
      requirements/
        R-<comp>-NNN.md  # one Behavior requirement each
      interface/
        cli.md           # CLI contract
        library.md       # library/function contract
        data/
          <TypeName>.md   # one schema/type each
        guarantees/
          G-<comp>-NNN.md # one behavioral/non-functional guarantee each,
                          # that a *dependent* may rely on (D16) — optional,
                          # like cli.md/library.md
      acceptance/
        AC-<comp>-NNN.md  # one acceptance criterion each
      constraints.md      # non-functional requirements (stays one file —
                           # see §3.4; no `Covers:`-style reference ever
                           # addresses one constraint individually)
  decisions/           # ADR-style, append-only, immutable once ratified
  glossary.md          # canonical vocabulary
SPEC_GUIDELINES.md      # this file
gen/                   # generated code
pipeline/              # workflow definitions, frozen prompts, model pins, toggles
verification/          # generated tests, contract checks, corpus-graph.json
tools/                 # hand-written repo-maintenance/authoring scripts —
                       # outside the spec-driven pipeline entirely (not
                       # generated, not gated, never read by any rule in
                       # this document). Scaffolding convenience only.
notes/                 # brainstorming — non-normative, not read by the pipeline
.hotdocs/              # LOCAL ONLY, gitignored — merge-tracking records
  tracking/            # (merge-tracker, D22) one record per merge attempt
  attempts/            # (merge-tracker, D32) one record per per-component
                       # generation+verification attempt, full detail —
                       # what D31's retired best-of-k loop used to fold
                       # into one provenance manifest, now the only place
                       # a blocked attempt's detail survives at all
  calls/               # (llm-endpoint, D32) one record per model call,
                       # caller-agnostic, transport-level only
                       # All of the above: never committed, never read by
                       # any gate's pass/fail decision — purely observability.
```

- `specs/` **MUST NOT** contain executable code of any kind, generated or
  hand-written. (D4)
- `gen/` and `verification/` **MUST** be committed on every branch. Large
  generated binary assets **MUST** go through Git LFS rather than a plain blob
  commit. (D6)
- Nothing under `gen/` or `verification/` is hand-edited, with exactly two
  declared exemptions — see §8.
- `.hotdocs/` **MUST** be gitignored and **MUST NOT** be read by any gate's
  pass/fail decision — it is observability data about past merge attempts,
  never an input to the current one. This is a correctness boundary, not
  just a storage convention: letting a gate's decision depend on local,
  uncommitted history would break every determinism/purity requirement
  elsewhere in this document (e.g. `impact-analyzer`'s R-IMPACT-006).
- `tools/` is committed (unlike `.hotdocs/`) but otherwise occupies the
  same "outside the methodology" position: a script here **MUST NOT** be
  invoked by `merge-orchestrator` or any gate, and **MUST NOT** write to
  `specs/`/`gen/`/`verification/` on a human's behalf without the human
  reviewing the result before committing — it may *create* new, empty
  scaffolding (directory structure, placeholder frontmatter), never
  author normative content. The distinction that matters: a scaffolding
  script removes mechanical friction; it does not do the spec-authoring
  work D1 reserves for a human or an assist agent.
- A `README.md` anywhere under `specs/` is non-normative scaffolding, not a
  governed spec — the linter and every other tool in this document **MUST**
  skip it. The governed set under a component directory is exactly:
  `component.md`; every file under `requirements/`, `interface/` (including
  `interface/data/`), and `acceptance/`; and `constraints.md`. Elsewhere: any
  other named `.md` file directly under `specs/product/`,
  `specs/architecture/`, `specs/vars/`, or `specs/decisions/`; and
  `specs/glossary.md`. (Found while bootstrapping `spec-linter` — nothing
  previously said how to tell a real spec from a placeholder sitting in the
  same directory.)
- **Why one file per unit, not one file per document type.** A component's
  individually-addressed units — each requirement, each acceptance criterion,
  each interface section — get their own file; narrative/frontmatter does
  not. This replaced an earlier four-flat-files design (`spec.md` /
  `interface.md` / `acceptance.md` / `constraints.md`) once it became clear
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

Frontmatter lives in exactly one place per component: **`component.md`**,
the root file. Every other file in a component — each `requirements/R-*.md`,
each `interface/cli.md` / `interface/library.md` / `interface/data/*.md`,
each `acceptance/AC-*.md`, and `constraints.md` — carries **no frontmatter
at all**. A unit file's identity is its filename and its position in the
directory tree; there is nothing left for frontmatter to declare. (This
replaced an earlier, less uniform rule — "only `spec.md` carries the full
field set, the other three carry `id`/`title`/`status`/`owners`" — once the
component was split into one-file-per-unit: there's no longer a meaningful
"this sub-file's own id/status" to track separately from the root's.)

A product capability (`specs/product/<name>.md`), an architecture doc
(`specs/architecture/<name>.md`), a var declaration (`specs/vars/<name>.md`),
and a decision record (`specs/decisions/<id>.md`) each remain one flat file
and carry the full field set below, same as `component.md` does for a
component (minus the component-only fields, naturally — a product capability
has no `sealed`, for instance). `specs/glossary.md` has no frontmatter at
all, same as before.

"Required" below is one of: **always** (every instance of this field is
mandatory), **never** (optional everywhere), or a stated **condition**
(mandatory only when the condition holds, forbidden otherwise — not merely
optional).

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | always | Stable identifier for the whole spec document (`component.md`, a product capability, etc.). A unit file's own id is its filename (e.g. `R-FOO-001.md`), not a frontmatter field — there is no unit-level frontmatter to hold one. |
| `title` | always | Human-readable name. |
| `status` | always | `draft` \| `ratified` \| `deprecated`. |
| `owners` | always | Who (human or team) is accountable for this spec. |
| `depends_on` | never (optional) | List of spec ids this one requires. Forms the dependency graph (D2). **(component `component.md` only)** |
| `realizes` | condition: required unless `sealed: true` | List of `P-<id>`s this component contributes to. (D8) **(component `component.md` only)** |
| `uses_var` | never (optional) | List of `VAR-<id>`s this component reads from `specs/vars/`. (D12) **(component `component.md` only)** |
| `depends_on_guarantees` | never (optional) | List of `G-<comp>-NNN` ids — a **strictly opt-in narrowing** of which of a dependency's `interface/guarantees/` entries this component actually relies on. (D16) **(component `component.md` only)** |
| `supersedes` | never (optional) | Prior spec id this one replaces. |
| `model_pin` | never (optional); **inapplicable when `sealed: true`** | Per-spec override of the repo-wide canonical model. **MUST** be omitted (not filled with a placeholder) on a sealed component — there is no generation to pin. **(component `component.md` only)** |
| `sealed` | never (optional), default `false` | Legacy-perimeter escape hatch — and, per the `criterion-compiler` precedent, also the correct mechanism for a *permanently* hand-maintained trust anchor, not only temporary legacy debt. See §8. (D1/D8) **(component `component.md` only)** |
| `source_path` | condition: required when `sealed: true`, forbidden otherwise | Where the actual, hand-maintained code lives. **MUST NOT** point under `gen/`. **(component `component.md` only)** |
| `last_ratified_commit` | condition: required when `status: ratified` | Commit hash of the ratifying merge. |

**Rules:**
- A spec **MUST NOT** be `status: ratified` while it has any non-empty `Open
  questions` section.
- `depends_on` **MUST** form an acyclic graph across the whole corpus.
- Every `depends_on`, `realizes`, and `uses_var` reference **MUST** resolve to
  a real, existing spec id. Dangling references are a hard lint failure.
- Every `depends_on_guarantees` entry **MUST** resolve to a real `G-<comp>-NNN`
  id, **and** that id's owning component **MUST** already be listed in this
  component's own `depends_on` — referencing a guarantee of a component you
  don't even depend on is meaningless, not just unresolved. (D16)
- `sealed: true` **MUST** carry a `source_path`; `sealed: false` or absent
  **MUST NOT** carry one.
- A `specs/vars/` declaration's own fields (`required`/`optional`, `type`,
  `description`, `sensitivity`, `example`/`default`) live in the document
  **body**, as bullets, not in frontmatter — its frontmatter is just `id` /
  `title` / `status` / `owners`. (A var declaration is a single flat file,
  not split into units — there's exactly one thing in it to address.)
- A unit file under `requirements/`, `interface/`, or `acceptance/`, or
  `constraints.md`, **MUST NOT** carry any frontmatter block at all. Finding
  one is a hard lint failure — the same structural guarantee that used to
  rely on a convention ("only `spec.md` has the full set") now holds by
  construction instead.

---

## 3. Document types

### 3.1 Product capability (`specs/product/<name>.md`)

Declares a capability with a stable `P-<id>`. Body: Purpose, Scope, and one or
more Given/When/Then golden scenarios (§5 format) exercised **black-box
against the whole assembled system** — never against one component in
isolation. (D8)

### 3.2 Architecture (`specs/architecture/<name>.md`)

The only place the component decomposition itself is declared and changed.
Splitting or merging components is **not** a normal spec change — it **MUST**
go through this area, as its own reviewed operation, distinct from an ordinary
component spec edit. (D2)

### 3.3 Var declaration (`specs/vars/<name>.md`)

Declares one configuration parameter. Fields: `name`, `required` \|
`optional`, `type` (`string` \| `url` \| `connection-string` \| `secret-ref` \|
`integer` \| `enum` \| …), `description`, `sensitivity` (`secret` \|
`non-secret`). (D12)

- There **MUST NOT** be a `value` field anywhere in this schema. Not a
  convention — the field does not exist.
- A declaration with `sensitivity: secret` **MUST NOT** carry an `example` or
  `default` field.
- A component that reads this variable **MUST** reference it via `uses_var`,
  never redefine its meaning locally.

### 3.4 Component (`specs/components/<name>/`)

One root file plus three unit directories plus one flat file:

**`component.md`** — the root. Carries the frontmatter (§2) and this fixed
section order:

| Section | Rule |
| --- | --- |
| Purpose | One paragraph: what this unit does and why it exists — **dependent-safe** (D34): no decision citations (`D<N>`), no historical justification, no cross-references to how this design was arrived at. This is the one section a *dependent* may see as part of its own context (`notes/backlog.md`'s "context" idea, once built) — everything that would make it internal rationale instead of a clean description belongs in Rationale, not here. |
| Rationale | Everything Purpose used to carry that isn't dependent-safe: decision citations, historical justification, cross-references to the discussion that produced this design. **Internal only** — never included in anything assembled for a dependent. Optional: a component whose Purpose genuinely needs no supporting history MAY omit this section entirely, rather than leave it empty for form's sake. |
| Scope | Explicit in-scope / out-of-scope bullets. |
| Definitions | Only deltas from `glossary.md`. |
| Behavior | Pointer: "See `requirements/`." |
| Interfaces | Pointer: "See `interface/`." |
| Data | Pointer: "See `interface/data/`." |
| Acceptance criteria | Pointer: "See `acceptance/`." |
| Non-functional constraints | Pointer: "See `constraints.md`." |
| Open questions | **MUST** be empty when `status: ratified`. |
| Change log | Human-readable history. |

**`requirements/R-<comp>-NNN.md`** — one normative requirement per file,
using RFC 2119 keywords. The filename *is* the requirement's id — no
frontmatter, no separate id field to keep in sync with it.

- Every `R-id` **MUST** be traceable forward to ≥1 acceptance criterion and
  backward to a rationale or decision record.
- A spec is not "done" until an authoring/generation agent can execute it with
  zero clarifying questions. An agent that must ask one **MUST** surface it as
  a tracked assumption or an open question, never silently guess.

**`interface/`** — the public contract (types, endpoints, events, CLI,
*and* behavioral guarantees — D16 extended "the contract" to include the
last of these, not just type signatures), split by kind:
- `interface/cli.md` — the CLI contract, if any.
- `interface/library.md` — the library/function contract, if any.
- `interface/data/<TypeName>.md` — one schema/type per file.
- `interface/guarantees/G-<comp>-NNN.md` — one behavioral/non-functional
  guarantee per file, that a *dependent* is entitled to rely on
  (consistency, ordering, idempotency, error-handling semantics, latency
  bounds). Like a requirement, each uses RFC 2119 keywords and its
  filename is its id. **Not** a place for internal implementation
  rationale — that stays in `requirements/`/`constraints.md`. (D16)

A component need not have all four — e.g. a purely-library component may
have no `cli.md`, and most components have no `guarantees/` at all (nothing
externally relied upon beyond ordinary types). The generated interface
**MUST** match this content exactly; any divergence is a hard drift-check
failure.

**`acceptance/AC-<comp>-NNN.md`** — one acceptance criterion per file. See
§5 for its internal format. The filename is the criterion's id.

**`constraints.md`** — stays one flat file, non-functional requirements
(perf, security, compatibility), each with a measurable target and a
measurement method. Deliberately **not** split like the three directories
above: nothing elsewhere in the corpus addresses one individual constraint
by id the way `Covers:`/`realizes`/`uses_var` address a requirement,
criterion, or interface section — there's no reference-granularity reason to
pay the extra-file cost here.

### 3.5 Decision record (`specs/decisions/<id>.md`)

ADR-style. Append-only. Once a decision record is ratified it is immutable —
a change in direction is a new, superseding record (`supersedes` field), never
an edit to the old one.

### 3.6 Glossary (`specs/glossary.md`)

Single file, no frontmatter, no per-spec entry limit. (D14)

- Specs **MUST** use glossary terms as defined; a component's `Definitions`
  section may only add deltas, never silently redefine a glossary term.
- **MUST NOT** be sharded by a size rule. The only legitimate split is a
  deliberate `architecture/`-level bounded-context decision (two subsystems
  that genuinely don't share vocabulary) — never a routine response to word
  count.

---

## 4. Component sizing

A component **MUST** be split when its full public behavior cannot be
captured by *complete*, agent-checkable acceptance criteria (§5's three
`kind`s all count toward completeness — a component is not oversized merely
because some of its behavior is legitimately judgment-based). This is the
non-negotiable trigger. (D2)

Below that bar, size caps are linter-enforced:

| Dimension | Warn above | Hard fail above |
| --- | --- | --- |
| Generated code per component | 800 LOC | 1500 LOC |
| Spec bundle (`component.md` + everything under `requirements/`, `interface/`, `acceptance/` + `constraints.md`) | 2000 words | 4000 words |
| Requirements (`R-id`s) per component | 20 | 40 |
| Public interface surface elements | 10 | 20 |
| `depends_on` count (fan-out) | 7 | — (warn only) |
| Dependents count (fan-in) | 10 | — (warn only) |
| Guarantees (`G-id`s) per component (D29) | 5 | 10 |
| Acceptance criteria (`AC-id`s) per component (D29) | 25 | 50 |
| **Per-file** words, for any single file under `requirements/` or `acceptance/` (D29) — distinct from the spec-bundle row above, which is a whole-bundle aggregate | 250 | 500 |
| **`Purpose` section** words (D35) — checks the "one paragraph" rule above mechanically; distinct from both rows above, scoped to one section, not a file or the bundle | 80 | 150 |

The last three rows are a first pass (D29), calibrated against this
corpus's own content at the time they were added rather than an a
priori judgment — expect them to be revisited as more components
exercise them. `guarantee_count` in particular had no cap at all
before: the interface-surface-elements row deliberately excludes
`interface/guarantees/` (a promise, not a callable surface element — see
`_count_interface_surface`'s own docstring), which meant an unbounded
number of guarantee files could previously accumulate with zero signal.

Components are a **flat namespace** — no nesting. `architecture/` is the only
place subsystem grouping is expressed.

**A decomposition signal, not just a cap to satisfy.** A single dimension
running high can be an accepted shape on its own — a thin coordinator
legitimately has wide fan-out with little owned logic of its own (see
`specs/architecture/pipeline-decomposition.md`'s note on
`merge-orchestrator`). But when **two or more independent dimensions**
above crowd their ceilings **for the same component at the same time**,
treat that as a sign the component owns a cross-cutting concern that has
outgrown its placement, not as evidence the caps themselves are
miscalibrated. This is enforced directly, not just described here: `spec-
linter`'s `R-LINT-022` (`D28`) emits a distinct finding whenever it fires.
Two shapes of this have shown up in practice so far, not just one: a thin
coordinator crowding fan-out together with spec-bundle words
(`merge-orchestrator`, resolved by `D25`), and a self-contained component
with no fan-out at all crowding spec-bundle words together with its own
requirement/acceptance/generated-code counts instead (`spec-linter`
itself, after `D29` added those dimensions — fan-out is irrelevant there;
the signal is still real). Fan-out measures how many neighbors a
component calls; the count/words dimensions measure how much it owns
directly. A thin coordinator runs fan-out high without the others; a
dense, isolated component can crowd several of the others with zero
fan-out. Either combination means the component isn't just one simple
shape (thin-and-wide, or fat-but-isolated) — it's carrying more than one
dimension's worth of cost at once.

The fix is not automatically a bigger cap, but it is also not
automatically a split — the signal means "look closely," not "extract
something." Start by asking whether a structural precedent for a split
already exists elsewhere in the corpus: `D25` extracted
`golden-scenario-verifier` out of `merge-orchestrator` once both caps
crowded at once, because that logic was already the cross-component
analog of `verifier-orchestrator`'s existing per-component dispatch — the
split mirrored a pattern already present, it wasn't invented from
scratch. Expect fan-out itself **not** to drop from such a split — the
coordinator still has to call the new component — the dimension that
should actually move is spec-bundle words.

Sometimes the honest conclusion is that no precedent exists and no split
is warranted: `spec-linter` crowding `generated_code_loc`,
`requirement_count`, and `spec_bundle_words` together reflects one
cohesive component with many genuinely independent, correlated rules —
not a hidden second responsibility with some other component's shape to
borrow. Splitting a single-pass structural linter into sub-checkers for
no architectural reason would be the wrong response to this signal, not
the right one; treat the signal as a prompt to check for a real
precedent, not a mandate to always act on it. If fan-out was the *only*
dimension crowding, that's a different, already-accepted case —
D2's "thin coordinator" shape, not this signal at all.

---

## 5. Acceptance criteria

Each file under a component's `acceptance/` directory (or, for a product
capability, each golden scenario inline in its one file) is a **Given/
When/Then block**, written in Gherkin syntax, with a required `Covers:` tag
(`@covers:<id>`) and a required `kind`. `Covers:` takes an `R-<id>` for a
component criterion, or a `P-<id>` for a product capability's own golden
scenario (D8) — product-level scenarios have no component `R-id` to
reference, only their own capability id:

| `kind` | How it's checked | Use when |
| --- | --- | --- |
| `compiled` | Deterministically compiled to test scaffolding — no model involved. Default. | The criterion is expressible in Given/When/Then and concerns runtime behavior of generated code. |
| `generated-test` | An agent writes test code from freeform prose; executed thereafter like any other test. | Runtime behavior that resists the Given/When/Then grammar. |
| `llm-judge` | An agent evaluates the criterion directly against an artifact — no code produced. | Qualities that are not runtime behavior at all (spec hardening, absence of contradiction, clarity). |

Rules:
- Every criterion, of any `kind`, **MUST** carry a `Covers:` tag referencing a
  real `R-<id>` (component) or `P-<id>` (product capability) — never a
  dangling reference.
- Prefer `compiled`, then `generated-test`; reach for `llm-judge` only when no
  test could capture the criterion even in principle. (D5)
- Generated test code **MUST** live under `verification/`, never under
  `specs/`. (D4)
- A `generated-test` criterion's mutation score **MUST** meet 80% (general) or
  90% (freeform-derived) or the merge fails.
- An `llm-judge` criterion **MUST** emit structured rationale alongside its
  verdict, for audit — the rationale is never itself a review gate.

---

## 6. Verification gates

Run per merge, scoped to the components in the impact-analysis blast radius:

1. **Spec lint** — structure, frontmatter, RFC 2119 usage, no open questions in
   ratified specs, glossary conformance, acyclic dependency graph, full
   traceability closure (every `R-id`, `realizes`, `uses_var`, `depends_on`,
   `depends_on_guarantees` reference resolves), size caps.
2. **Generation** — the pinned canonical model, cold, no prior code, from the
   spec bundle (`component.md` + `requirements/` + `interface/` +
   `constraints.md` + depended-upon components' `interface/` + referenced
   `specs/vars/` declarations + `glossary` — deliberately excluding
   `acceptance/`, so the model doesn't overfit to its own tests). Exactly
   one attempt per component per merge — no automatic retry (D1/D31: the
   best-of-k retry this step used to run was retired; a failed attempt
   blocks the merge for that component, and a human re-running the merge,
   after reviewing the per-attempt record D32 requires, is the only path
   back to a fresh generation call). That re-run's one call MAY carry
   `retry_feedback` — the immediately preceding attempt's failing
   requirements — but only if the human explicitly supplies it (D33);
   nothing computes or injects it automatically.
3. **Per-criterion verification** — compiled / generated-test / llm-judge, per
   §5. Contract/property tests from `interface/`. A drift check that
   generated interfaces match `interface/`'s contract exactly.
4. **License scan** and **secrets scan** — automated, unconditional. A flag
   blocks the merge; the pipeline may retry generation without escalating to
   a person. Every flag (clean or not, resolved or not) is written to the
   provenance manifest and the review packet — never silent. A flag above a
   severity threshold notifies a
   standing compliance channel. (D7/D12)
5. **Golden-scenario verification** — once every component in the blast
   radius has regenerated and passed its own per-component verification
   (steps 2–3), run the golden scenarios of every product capability whose
   `realizes`-set intersects the blast radius, against the real, fully
   assembled `gen/` output — not a prediction, the actual regenerated
   system. A failure blocks the merge the same way a per-component
   verification failure does. This is the backstop for cross-component
   behavioral risk that no amount of interface-level diffing can rule out
   in principle (D16) — not a redundant check: `interface/guarantees/`
   (D16) makes *foreseen* behavioral dependencies explicit and propagating,
   this gate catches what wasn't foreseen.
6. **Non-functional gates** where feasible (benchmarks, size budgets).
7. **Review packet** — spec diff, changed requirements, regenerated
   components, verification results, residual risk, license/secret flags,
   cache-hit status, golden-scenario results, and any new/changed
   `sealed`/override declarations. A human reviews this and the spec diff.
   **No human review of generated code is required, of any kind.** (D5)
8. **Merge** — `specs/`, `gen/`, and `verification/` (including
   `corpus-graph.json`) update atomically in one squashed commit.

A merge whose spec bundle exactly matches an already-verified prior state
**MUST** be treated as a cache hit across the entire gate stack (cache key:
`spec_bundle_hash`, `artifact/gate-inputs hash`, `gate_version`, `model_pin`)
— restore the matching artifacts, skip regeneration and re-verification, but
**never** skip the human spec-diff review. The non-spec-driven-change lane
still re-runs asynchronously afterward as an environment-drift safety net.
(D11/D13)

A gate's `gate_version` **MUST** bump whenever its underlying detection logic
changes (e.g. the license scanner's signature database), so a cache hit never
papers over a genuinely changed risk.

---

## 7. Provenance

Every generated artifact carries `.provenance.json` alongside it (in
`gen/<component>/` and `verification/<component>/`), committed under the same
discipline as the artifact itself:

```
spec_bundle_hash    content hash of every spec file that fed generation
model_pin           model id + version
prompt_version      id of the frozen prompt template used
retry_feedback      R-id list the caller supplied for this call, if any
                    (R-GEN-012, D33) — null if the call was blind. No
                    sample_index: D31 retired same-merge retry, so there
                    is no "which sample" left to record, only whether
                    this one call was informed.
pipeline_version    version of the generation pipeline itself
gate_versions       per-gate version map (compiler, license_scanner,
                     mutation_harness, secret_scanner, ...)
cache_hit           bool — if true, the fields below are copied from the
                     matching prior commit, not freshly computed
generated_at
verification_run_id
verification_report  the VerificationReport (verifier-orchestrator)
license_scan        result (license-scanner)
secret_scan         result (secret-scanner) — missing from an earlier draft
                     of this schema even though gate_versions already
                     expected a secret_scanner entry; found while specifying
                     provenance-writer, which is what actually assembles
                     this file from every other component's output
```

This is the evidence trail for incident debugging (is this a spec bug or a
generation bug?) and doubles as an SBOM/SLSA-style attestation.

---

## 8. Exemptions from cold regen

Exactly two, both declared and tracked — never silent:

**Sealed components** (component granularity). `sealed: true` + `source_path`.
The component's spec says only "matches existing behavior; do not
regenerate." Its code lives at `source_path`, **MUST NOT** be under `gen/`.
Exempt from `realizes` and the cold-regen invariant. **MUST** have
characterization tests in `verification/<component>/` the normal way —
wrapping legacy code in traceability doesn't require rewriting it.

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

## 10. What this document does not cover

Implementation details — the actual linter, the generation pipeline's code,
prompt templates, the corpus-graph renderer — live under `pipeline/` and
`verification/` and are not specified here. This document is the contract
those implementations must satisfy, not the implementation itself.
