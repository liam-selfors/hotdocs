---
id: comp-criterion-compiler
title: Criterion Compiler
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
sealed: true
source_path: pipeline/criterion-compiler/
---

# Criterion Compiler

## Purpose

Deterministically compiles `kind: compiled` Given/When/Then acceptance
criteria into executable test scaffolding, with no model involved at any
step. It is the trust anchor for `compiled`-kind criteria (D5/D4): `compiled`
criteria are the strongest tier of evidence specifically *because* nothing
agent-generated sits between the criterion and the check — and that argument
only holds if the compiler itself is not agent-generated. It is therefore
**permanently sealed** (`sealed: true`), not as legacy debt being wrapped
(§8's original framing for `sealed`) but as a deliberate, permanent design
choice: if this component lived under `gen/`, trusting a `compiled` criterion
would mean trusting an agent-generated compiler to correctly compile
agent-generated tests for agent-generated code — a circularity `compiled`
exists specifically to avoid. See `specs/architecture/pipeline-decomposition.md`
for the fuller rationale.

## Scope

**In scope:** parsing the fixed Given/When/Then step grammar
(`specs/architecture/step-phrase-grammar.md`); resolving step references
against a component's `interface/` contract; emitting deterministic test
code under `verification/<component>/compiled/`; failing loudly and
specifically on any step that doesn't parse or doesn't resolve.

**Out of scope:** `generated-test` and `llm-judge` criteria (handled
elsewhere); anything requiring natural-language understanding — the step
grammar is intentionally small and fixed, not open English, precisely so this
component never needs a model call (see Non-functional constraints).

**A circularity this component's own acceptance criteria must resolve:**
nothing in this spec's Acceptance Criteria section can itself be
`kind: compiled` — that would mean using the compiler to verify the compiler,
which proves nothing about whether the compiler is correct independent of its
own bugs. Resolved as `kind: generated-test` throughout (see
`acceptance/`): an agent writes test code from this spec's prose,
independent of — and with no access to — this component's hand-maintained
implementation. The usual `generated-test` trust argument ("independent
generation path, different model than the code under test") was framed in
D5 for *generated* code under test; here the code under test is hand-written,
not generated, which if anything makes the test's independence from it
*stronger*, not weaker — but this is a real gap in how D5 phrased that
mechanism, worth a note back to `notes/initial-ideas.md` (flagged, not
silently resolved by just reusing the label).

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/` (`CompileReport` schema). The step-grammar reference
itself lives at `specs/architecture/step-phrase-grammar.md`, not here — see
Purpose above for why.

## Acceptance criteria

See `acceptance/`. All `kind: generated-test`, not `compiled` — using the
compiler to verify the compiler would prove nothing about correctness
independent of the compiler's own bugs (see Purpose above). An agent writes
these tests from this prose, with no access to the hand-maintained
implementation at `pipeline/criterion-compiler/` — the same independence
argument `generated-test` normally makes between an agent's test and an
agent's *generated* code, just applied here between an agent's test and a
*human's* code, which is at least as independent.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Canonical target test framework/language for emitted scaffolding — is a
  single fixed target acceptable for v1, or does multi-target emission need
  to be designed in now?~~ — resolved: single fixed target (`pytest`) for
  v1, confirmed (R-COMPILE-011); no multi-target machinery designed in now.
  Safe to defer because the grammar (`specs/architecture/
  step-phrase-grammar.md`) was already written in target-independent terms
  — each template's "compiles to" column describes a bound fact ("a call to
  the named function," "an equality assertion on `result.<path>`"), never
  pytest syntax specifically. R-COMPILE-011 makes that separation a formal
  requirement (parse+bind vs. emit) so a future second target is an
  additive emitter, not a grammar rework — without adding any
  plugin/registry abstraction nobody has asked for yet.
- ~~Where the published step-phrase grammar itself is versioned and
  reviewed~~ — resolved, and since D15, physically relocated too:
  `specs/architecture/` owns "cross-cutting tech decisions" by its own
  definition (`notes/initial-ideas.md` §4), and the grammar is exactly
  that — a corpus-wide structural decision, not a component behavior or a
  product capability. The detailed table now lives at
  `specs/architecture/step-phrase-grammar.md` itself (no longer just
  governed-there-while-living-in-`interface/`), carrying the same
  governance weight as splitting a component (D2) — not a routine
  `criterion-compiler` spec edit.
- Exact boundary of "literal data" in R-COMPILE-007 — are template
  interpolations (e.g. referencing a previously-bound fixture name inside a
  later step) literal, or does that cross into expression evaluation?

## Change log

- Initial draft.
