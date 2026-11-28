---
id: comp-corpus-loader
title: Corpus Loader
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine]
realizes: [P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Corpus Loader

## Purpose

Reads a spec corpus into one in-memory model: every spec file
classified, its frontmatter parsed, the components assembled from their
files, and the shared graph views loaded, so every component that needs
the corpus reads the same structure.

## Rationale

See `D242`.

## Scope

**In scope:** `load_corpus` and the `Corpus` model.

**Out of scope:** judging the corpus; every rule lives in `spec-linter`,
`citation-checker` or `size-checker`.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D242`.
