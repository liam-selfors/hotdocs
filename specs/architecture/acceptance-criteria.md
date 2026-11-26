---
id: arch-acceptance-criteria
title: Acceptance Criteria
status: draft
owners: [pipeline-team]
depends_on: []
---

# Acceptance Criteria

The format and rules of acceptance criteria and capability scenarios,
and where the code they check lives, moved here from
`SPEC_GUIDELINES.md` so a component that checks or runs them reads only
these (`D381`).

## Format

Each file under a component's `acceptance/` directory (or, for a product
capability, each capability scenario inline in its one file) is a **Given/
When/Then block**, written in Gherkin syntax, with a required `Covers:` tag
(`@covers:<id>`) and a required `kind`. `Covers:` takes an `R-<id>` for a
component criterion, or a `P-<id>` for a product capability's own
capability scenario (D8):

| `kind` | How it's checked | Use when |
| --- | --- | --- |
| `compiled` | Deterministically compiled to test scaffolding — no model involved. Default. | The criterion is expressible in Given/When/Then and concerns runtime behavior of generated code. |
| `generated-test` | An agent writes test code from the criterion's Given/When/Then text, whose steps may be free prose; executed thereafter like any other test. | Runtime behavior the compiled step grammar cannot express. |
| `llm-judge` | An agent evaluates the criterion directly against an artifact — no code produced. | Qualities that are not runtime behavior at all (spec hardening, absence of contradiction, clarity). |

## Rules

- Every criterion, of any `kind`, **MUST** carry a `Covers:` tag referencing a
  real `R-<id>` (component) or `P-<id>` (product capability) — never a
  dangling reference.
  An acceptance file's tag is its first `Covers:` followed by the id;
  any later `Covers:` in the file is prose or an example, never a
  reference (`D232`). A capability scenario's is the `Covers:` line
  directly under its `### CS-...` heading. The `kind` is the line
  `Kind: <kind>` (capital K, one of the three values above) that
  follows the tag, never a frontmatter field (`D234`).
- Prefer `compiled`, then `generated-test`; reach for `llm-judge` only when no
  test could capture the criterion even in principle. (D5)
- Generated test code **MUST** live under `verification/`, never under
  `specs/`. (D4)
- Every criterion file **MUST** hold at least one line starting `Given`,
  one starting `When` and one starting `Then` (`R-LINT-010`); a file
  without them fails lint, whatever its `kind`.
- A `generated-test` criterion's mutation score **MUST** meet 80% (general) or
  90% (freeform-derived) or the merge fails. (D80)
- An `llm-judge` criterion **MUST** emit structured rationale alongside its
  verdict, for audit — the rationale is never itself a review gate.
- A component with an `interface/cli.md` **MUST** have a requirement that
  cites `interface/cli.md` by that path and pins its argument parsing:
  each flag's accepted forms (`--flag=value` and/or `--flag value`), what
  a flag given with no value does, how a wrong subcommand or unknown
  argument is handled, which flags pass through to the library call,
  and every exit code. At least one criterion **MUST** cover it,
  exercising each of those cases. (`R-LINT-031`, D162) Its finding is
  reported on the component's `interface/cli.md`, at line 1.
- Every behavior a criterion checks **MUST** be stated in a requirement
  or the interface: the generator never sees `acceptance/`, and
  implements only what its bundle states. (D298)
- Every fact a criterion's test needs (a value, file layout, reply
  format, error category, flag or grammar form) **MUST** appear in that
  criterion, the one requirement it covers, or the component's interface
  with its `Implements:` documents: nothing else reaches its test
  author. A rule several criteria share belongs in the interface or a
  `specs/architecture/` document. `hotdocs spec check` reports
  violations. (D298, D300)
- A criterion **SHOULD** name concrete inputs and exact expected outputs,
  and the exception class or exit code of every failure it expects.

## Code under test

A component's real code under `gen/<slug>/` (`<slug>` per
`glossary.md`'s "Component id / component slug" entry) **MUST** be
either a flat `<slug_with_underscores>.py` module or a
`<slug_with_underscores>/` package (with `__init__.py`) directly
under `gen/<slug>/` — never nested deeper (e.g. a `src/` layout) and
never a separately-installed distribution. `spec-bundle-assembler`'s
`dependency_usage` (`R-ASSEMBLE-011`, `D37`) only ever looks in those
two exact locations (`D46`).
