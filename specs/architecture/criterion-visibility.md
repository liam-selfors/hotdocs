---
id: arch-criterion-visibility
title: What Each Model Sees, and Where a Rule Must Be Written
status: draft
owners: [pipeline-team]
depends_on: []
---

# What each model sees, and where a rule must be written

## Purpose

Every model in the pipeline works from a fixed slice of the spec and
cannot ask for more. This document states each slice and the two rules
that follow, so a spec can be checked against them before generation
(`D298`).

## The slices

- **The generator** sees a component's `SpecBundle`
  (`spec-bundle-assembler`'s `interface/data/SpecBundle.md`): its
  `component.md` body, `requirements/`, `interface/` with every document
  its `interface/library.md` names on an `Implements:` line,
  `constraints.md`, each dependency's `interface/`, `Purpose` and usage
  card, its vars, and the glossary. It never sees `acceptance/` or any
  test.
- **A criterion's test author** sees that criterion's `CriterionBundle`
  (`verifier-orchestrator`'s `R-VERIFY-009`): the criterion's own text,
  the text of the one requirement its `Covers:` names, the component's
  `interface/` with its `Implements:` documents, each dependency's
  `interface/`, and the glossary. It never sees another criterion,
  another requirement, `constraints.md`, a decision record or the code.
- **The judge** of an `llm-judge` criterion sees the criterion, its
  covered requirement, the interface and the component's code.

## The rules

1. **Stated behavior.** Every behavior a criterion checks MUST be stated
   in a requirement or in the interface. The generator implements only
   what its bundle states (`R-GEN-020`), so behavior named only in a
   criterion is behavior the code will not have.
2. **Visible rules.** Every fact a criterion's test needs, such as a
   value, file layout, reply format, error category, command-line flag or
   grammar form, MUST appear in that criterion, its covered requirement,
   or the interface. A fact written anywhere else is invisible to that
   test's author.

A rule several criteria share belongs in a document under
`specs/architecture/`, named on the component's `Implements:` line: it
then reaches the generator and every test author of that component.
