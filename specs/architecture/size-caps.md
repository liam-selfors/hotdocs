---
id: arch-size-caps
title: Size Caps
status: draft
owners: [pipeline-team]
depends_on: []
---

# Size Caps

When a component must be split, and the linter-enforced size caps below
that bar and how each is measured, moved here from `SPEC_GUIDELINES.md`
so a component that checks them reads only these (`D381`).

## Split trigger

A component **MUST** be split when its full public behavior cannot be
captured by *complete*, agent-checkable acceptance criteria (all three
`kind`s of `specs/architecture/acceptance-criteria.md` count toward
completeness — a component is not oversized merely because some of its
behavior is legitimately judgment-based). (D2)

Components are a **flat namespace** — no nesting. `architecture/` is the
only place subsystem grouping is expressed.

## Caps

Below that bar, size caps are linter-enforced:

| Dimension | Warn above | Hard fail above |
| --- | --- | --- |
| Generated code per component (`D79`) | 800 LOC | 1500 LOC |
| Generator bundle — `generator_words`: what the component's generator reads (its own `component.md` without Rationale, Open questions and Change log, `requirements/`, `interface/`, `constraints.md`, the documents its `Implements:` line appends, and each dependency's `interface/` and `Purpose`), from `graph-query-engine`'s `bundle_size` view (`R-GQE-009`, `D380`) | 8000 words | 14000 words |
| Largest criterion bundle — `criterion_words_max`: the words of the largest one criterion's test-author bundle (the criterion, its covered requirement, the component's `interface/` and appended documents, dependencies' `interface/`, and `testing.md`), from the same view | 6000 words | 12000 words |
| Requirements (`R-id`s) per component (`D79`) | 20 | 40 |
| Public interface surface elements (`D79`) | 10 | 20 |
| `depends_on` count (fan-out) (`D79`) | 7 | — (warn only) |
| Dependents count (fan-in) (`D79`) | 10 | — (warn only) |
| Guarantees (`G-id`s) per component (D17) | 5 | 10 |
| Acceptance criteria (`AC-id`s) per component (D17) | 25 | 50 |
| **Per-file** words, for any single file under `requirements/` or `acceptance/` (D17) | 250 | 500 |
| **`Purpose` section** words (D22) — checks the Purpose "one paragraph" rule of `specs/architecture/spec-layout.md` mechanically, scoped to one section, not a file or a bundle | 80 | 150 |

## How each dimension is measured

Per component directory `specs/components/<c>/` (`D211`):

- `generated_code_loc`: lines of every `*.py` file under `gen/<c>/`,
  recursively, that are neither blank nor, once stripped, start with `#`.
- `generator_words`: the `bundle_size` view's `generator_words`
  (`R-GQE-009`).
- `criterion_words_max`: the `bundle_size` view's `criterion_words_max`
  (`R-GQE-009`).
- `requirement_count`, `guarantee_count`, `acceptance_count`: the number
  of `R-*.md`, `interface/guarantees/G-*.md` and `AC-*.md` files.
- `interface_surface`: one per non-blank line of the first fenced block
  in `interface/cli.md` (a line ending in `\` joins the next), plus one
  per line of the first fenced block in `interface/library.md` matching
  `^\w+\(.*\)\s*(->|:)` after the same joining, plus one per file in
  `interface/data/`. Guarantees never count.
- `fan_out`: entries in `depends_on`. `fan_in`: components whose
  `depends_on` names this one.
- Per-file words (`R-SIZE-003`, `requirements/` and `acceptance/` files)
  and `Purpose` words: the number of whitespace-separated tokens
  (Python's `str.split()`) of the file's text after any frontmatter, or of
  the `Purpose` section's text between its heading line and the next
  `##` heading. Code blocks and headings count like any other text.
  (`D231`)

## Decomposition signal

When **two or more** of the dimensions above are over their *warn*
threshold **for the same component at the same time**, the linter emits
a distinct finding (`R-SIZE-002`, `D15`): a sign the component may own a
cross-cutting concern that has outgrown its placement, to look at
closely, never itself a hard failure.
