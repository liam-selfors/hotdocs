---
id: comp-spec-reviewer
title: Spec Reviewer
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-spec-bundle-assembler, comp-llm-endpoint]
realizes: [P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Spec Reviewer

## Purpose

Checks, before anything is generated, whether each acceptance criterion
can be implemented from what its test author will actually see, and
whether it expects behavior no requirement states. Reports what is
missing and, with a model, proposes the spec text that would close each
gap. Advisory only.

## Scope

**In scope:** for each criterion of the named components or criteria,
building the exact `CriterionBundle` its test author receives; a
deterministic check that every name the criterion references appears in
what that author can see; one model call per criterion asking what an
author would have to guess and what behavior goes unstated; lint of the
named components with the model-backed glossary judge (`R-LINT-015`);
writing proposals to `.hotdocs/proposals/` on request.

**Out of scope:** changing any spec file; gating anything; judging
whether a requirement is right.

## Definitions

A **gap** is a fact a criterion's test needs that its test author cannot
see, or a behavior the criterion checks that no requirement or interface
text states (`specs/architecture/criterion-visibility.md`).

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

All are `kind: generated-test`, with an injected mock model.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D300`: initial spec.
