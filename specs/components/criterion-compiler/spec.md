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

**In scope:** parsing the fixed Given/When/Then step grammar (§ below);
resolving step references against a component's `interface.md`; emitting
deterministic test code under `verification/<component>/compiled/`; failing
loudly and specifically on any step that doesn't parse or doesn't resolve.

**Out of scope:** `generated-test` and `llm-judge` criteria (handled
elsewhere); anything requiring natural-language understanding — the step
grammar is intentionally small and fixed, not open English, precisely so this
component never needs a model call (see Non-functional constraints).

**A circularity this component's own acceptance criteria must resolve:**
nothing in this spec's Acceptance Criteria section can itself be
`kind: compiled` — that would mean using the compiler to verify the compiler,
which proves nothing about whether the compiler is correct independent of its
own bugs. Resolved as `kind: generated-test` throughout (see
`acceptance.md`): an agent writes test code from this spec's prose,
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

- **R-COMPILE-001** — The compiler MUST recognize only the fixed,
  published step-phrase grammar (interface.md) for Given/When/Then steps, and
  MUST reject — with a specific, located compile error, never a best-effort
  guess — any step that does not match a recognized template.
- **R-COMPILE-002** — The compiler MUST resolve every function, endpoint, or
  type name referenced in a step against the target component's
  `interface.md`, and MUST fail to compile (not silently skip) any reference
  that does not resolve.
- **R-COMPILE-003** — Compiling the same `acceptance.md` + `interface.md`
  pair MUST always produce byte-identical generated test code. Required for
  D13's cache-key correctness.
- **R-COMPILE-004** — Compiled test output for a criterion MUST carry that
  criterion's `Covers:` id as metadata in the emitted code, so a failing test
  traces back to its `R-id`/`P-id` without re-parsing `acceptance.md`.
- **R-COMPILE-005** — The compiler MUST compile only criteria whose `Kind` is
  `compiled`; it MUST pass through, not error on, criteria of any other
  `kind` — those are handled by other mechanisms entirely.
- **R-COMPILE-006** — Compiled test code MUST be written under
  `verification/<component>/compiled/`, never under `specs/` (D4).
- **R-COMPILE-007** — A step's literal value arguments MUST be parsed as
  literal data (strings, numbers, JSON), never evaluated as code — the
  compiler MUST NOT become an arbitrary-code-execution vector via crafted
  Gherkin.
- **R-COMPILE-008** — The compiler MUST NOT invoke any model or agent at any
  stage of compilation; its entire behavior is grammar parsing, interface
  binding, and deterministic code emission.
- **R-COMPILE-009** — Recompiling an unchanged `acceptance.md` +
  `interface.md` pair MUST NOT change already-written output files (avoids
  spurious diffs, supports D11 cache-hit comparison).
- **R-COMPILE-010** — The compiler MUST report its own `gate_version` (D7),
  and that version MUST change whenever the step grammar or interface-binding
  rules change.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`CompileReport` schema, step-grammar reference).

## Acceptance criteria

See `acceptance.md`. All `kind: generated-test` — see Scope above for why
`compiled` is unavailable here.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Canonical target test framework/language for emitted scaffolding — this
  spec assumes Python + pytest-style test functions as a concrete default
  (interface.md), but the grammar itself doesn't require that target; is a
  single fixed target acceptable for v1, or does multi-target emission need
  to be designed in now?
- ~~Where the published step-phrase grammar itself is versioned and
  reviewed~~ — resolved: `specs/architecture/` already owns "cross-cutting
  tech decisions" by its own definition (`notes/initial-ideas.md` §4), and
  the grammar is exactly that — a corpus-wide structural decision, not a
  component behavior or a product capability. The detailed table stays here
  in `interface.md` (this component implements it), but
  `specs/architecture/pipeline-decomposition.md` now records that changing it
  is an architecture-level decision, not a routine `criterion-compiler` spec
  edit — same governance weight as splitting a component (D2).
- Exact boundary of "literal data" in R-COMPILE-007 — are template
  interpolations (e.g. referencing a previously-bound fixture name inside a
  later step) literal, or does that cross into expression evaluation?

## Change log

- Initial draft.
