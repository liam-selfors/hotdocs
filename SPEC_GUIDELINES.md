# Spec Guidelines

This document is the rulebook. Every authoring agent, generation agent, and
linter invocation in this repository follows it. It states **what** is
required; it does not re-derive **why** — the rationale and the decision
history live in `notes/initial-ideas.md` (`D1`–`D14`) and are cited here by
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
      spec.md          # normative behavior
      interface.md     # public contract
      acceptance.md    # acceptance criteria
      constraints.md   # non-functional requirements
  decisions/           # ADR-style, append-only, immutable once ratified
  glossary.md          # canonical vocabulary
SPEC_GUIDELINES.md      # this file
gen/                   # generated code
pipeline/              # workflow definitions, frozen prompts, model pins, toggles
verification/          # generated tests, contract checks, corpus-graph.json
notes/                 # brainstorming — non-normative, not read by the pipeline
```

- `specs/` **MUST NOT** contain executable code of any kind, generated or
  hand-written. (D4)
- `gen/` and `verification/` **MUST** be committed on every branch. Large
  generated binary assets **MUST** go through Git LFS rather than a plain blob
  commit. (D6)
- Nothing under `gen/` or `verification/` is hand-edited, with exactly two
  declared exemptions — see §9.

---

## 2. Universal frontmatter

Every file under `specs/` (except `glossary.md`) carries YAML frontmatter.
Fields marked **(component only)** apply to `specs/components/<x>/*.md`; all
others apply wherever relevant.

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable identifier. `R-<comp>-NNN` scheme for requirements (inline, not frontmatter); the spec file itself uses a document id. |
| `title` | yes | Human-readable name. |
| `status` | yes | `draft` \| `ratified` \| `deprecated`. |
| `owners` | yes | Who (human or team) is accountable for this spec. |
| `depends_on` | no | List of spec ids this one requires. Forms the dependency graph (D2). |
| `realizes` | **(component only)**, conditionally required | List of `P-<id>`s this component contributes to. Required unless `sealed: true`. (D8) |
| `uses_var` | **(component only)**, no | List of `VAR-<id>`s this component reads from `specs/vars/`. (D12) |
| `supersedes` | no | Prior spec id this one replaces. |
| `model_pin` | no | Per-spec override of the repo-wide canonical model. |
| `cross_model_divergence_check` | no | Per-spec override of the repo-wide toggle: `enabled` \| `disabled`. (D3) |
| `fallback_standby_build` | no | Per-spec override of the repo-wide toggle: `enabled` \| `disabled`. (D10) |
| `sealed` | **(component only)**, no, default `false` | Legacy-perimeter escape hatch. See §9. (D1/D8) |
| `source_path` | **(component only)**, required when `sealed: true` | Where the actual, hand-maintained code lives. **MUST NOT** point under `gen/`. |
| `last_ratified_commit` | yes when `status: ratified` | Commit hash of the ratifying merge. |

**Rules:**
- A spec **MUST NOT** be `status: ratified` while it has any non-empty `Open
  questions` section.
- `depends_on` **MUST** form an acyclic graph across the whole corpus.
- Every `depends_on`, `realizes`, and `uses_var` reference **MUST** resolve to
  a real, existing spec id. Dangling references are a hard lint failure.
- `sealed: true` **MUST** carry a `source_path`; `sealed: false` or absent
  **MUST NOT** carry one.

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

Four files, each with the frontmatter in §2 and the body rules below.

**`spec.md`** — fixed section order:

| Section | Rule |
| --- | --- |
| Purpose | One paragraph: why this unit exists. |
| Scope | Explicit in-scope / out-of-scope bullets. |
| Definitions | Only deltas from `glossary.md`. |
| Behavior | Normative requirements, each a stable `R-<comp>-NNN`, each using RFC 2119 keywords. |
| Interfaces | Contracts with worked examples. Generated code **MUST** match exactly. |
| Data | Schemas, invariants, migration rules. |
| Acceptance criteria | See §3.5 below — lives in `acceptance.md`, cross-referenced here. |
| Non-functional constraints | Measurable targets and how they're measured. |
| Open questions | **MUST** be empty when `status: ratified`. |
| Change log | Human-readable history. |

- Every `R-id` **MUST** be traceable forward to ≥1 acceptance criterion and
  backward to a rationale or decision record.
- A spec is not "done" until an authoring/generation agent can execute it with
  zero clarifying questions. An agent that must ask one **MUST** surface it as
  a tracked assumption or an open question, never silently guess.

**`interface.md`** — the public contract (types, endpoints, events, CLI). The
generated interface **MUST** match this file exactly; any divergence is a hard
drift-check failure.

**`acceptance.md`** — see §5.

**`constraints.md`** — non-functional requirements (perf, security,
compatibility), each with a measurable target and a measurement method.

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
| Spec bundle (`spec`+`interface`+`acceptance`+`constraints`) | 2000 words | 4000 words |
| Requirements (`R-id`s) per component | 20 | 40 |
| Public interface surface elements | 10 | 20 |
| `depends_on` count (fan-out) | 7 | — (warn only) |
| Dependents count (fan-in) | 10 | — (warn only) |

Components are a **flat namespace** — no nesting. `architecture/` is the only
place subsystem grouping is expressed.

---

## 5. Acceptance criteria

Each criterion in `acceptance.md` is a **Given/When/Then block**, written in
Gherkin syntax, with a required `Covers:` tag (`@covers:<id>`) and a required
`kind`. `Covers:` takes an `R-<id>` in a component's `acceptance.md`, or a
`P-<id>` in a product capability's golden scenarios (D8) — product-level
scenarios have no component `R-id` to reference, only their own capability
id:

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
   traceability closure (every `R-id`, `realizes`, `uses_var`, `depends_on`
   reference resolves), size caps.
2. **Generation** — the pinned canonical model, cold, no prior code, from the
   spec bundle (`spec` + `interface` + `constraints` + depended-upon
   interfaces + referenced `specs/vars/` declarations + `glossary`). Best-of-k
   retry (k = 2–4) against verification on failure; the winning sample index
   is recorded. (D1/D3)
3. **Per-criterion verification** — compiled / generated-test / llm-judge, per
   §5. Contract/property tests from `interface.md`/`Data`. A drift check that
   generated interfaces match `interface.md` exactly.
4. **Cross-model divergence check** — runs only when `cross_model_divergence_check`
   resolves to `enabled` (repo default: enabled when a second model is
   configured) **and** a second model is actually configured. Regenerates the
   component with that second model; a build that **passes verification but
   diverges behaviorally** from the canonical build **blocks the merge** as a
   spec defect. A build that **fails** verification outright does not block,
   but is logged. (D3)
5. **License scan** and **secrets scan** — automated, unconditional, run
   regardless of the toggle in step 4. A flag blocks the merge; the pipeline
   may retry generation without escalating to a person. Every flag (clean or
   not, resolved or not) is written to the provenance manifest and the review
   packet — never silent. A flag above a severity threshold notifies a
   standing compliance channel. (D7/D12)
6. **Non-functional gates** where feasible (benchmarks, size budgets).
7. **Review packet** — spec diff, changed requirements, regenerated
   components, verification results, residual risk, license/secret flags,
   cache-hit status, and any new/changed `sealed`/override declarations. A
   human reviews this and the spec diff. **No human review of generated code
   is required, of any kind.** (D5)
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

## 7. Toggles

Two independent, repo-wide settings in `pipeline/`, each overridable per-spec:

- **`cross_model_divergence_check`**: `enabled` | `disabled`. Default:
  `enabled` whenever a second model is configured.
- **`fallback_standby_build`**: `enabled` | `disabled`. Independent of the
  above — when the divergence check is off but a warm, promotable fallback
  build is still wanted, this keeps one generated and verified (not diffed or
  gated on) every merge, at lower cost than full divergence checking. (D10)

The tool **MUST** keep functioning with only one model configured. With both
toggles off (or no second model at all), an outage of the only configured
model **halts merges** until a human re-ratifies a working pin. This is an
accepted, explicit tradeoff — not a bug.

A second model from a different vendor than the canonical pin is **RECOMMENDED**,
never required.

---

## 8. Provenance

Every generated artifact carries `.provenance.json` alongside it (in
`gen/<component>/` and `verification/<component>/`), committed under the same
discipline as the artifact itself:

```
spec_bundle_hash    content hash of every spec file that fed generation
model_pin           model id + version
prompt_version      id of the frozen prompt template used
sample_index        which best-of-k sample won
pipeline_version    version of the generation pipeline itself
gate_versions       per-gate version map (compiler, license_scanner,
                     cross_model_check, mutation_harness, secret_scanner, ...)
cache_hit           bool — if true, the fields below are copied from the
                     matching prior commit, not freshly computed
generated_at
verification_run_id
cross_model_check   divergence-gate outcome
license_scan        result
```

This is the evidence trail for incident debugging (is this a spec bug or a
generation bug?) and doubles as an SBOM/SLSA-style attestation.

---

## 9. Exemptions from cold regen

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

## 10. Secrets

Unconditional, not a scope question:

- Secrets **MUST NOT** appear anywhere in `specs/`, `gen/`, or `verification/`.
- An automated secret-pattern scan runs pre-merge-gate and, where tooling
  allows, as early as pre-commit/pre-push.
- Config *contracts* (name, type, required/optional, description) belong in
  `specs/vars/`. Config *values*, and infra-as-code/provisioning, are **out of
  scope** for this methodology — conventionally managed, outside `specs/`.

---

## 11. What this document does not cover

Implementation details — the actual linter, the generation pipeline's code,
prompt templates, the corpus-graph renderer — live under `pipeline/` and
`verification/` and are not specified here. This document is the contract
those implementations must satisfy, not the implementation itself.
