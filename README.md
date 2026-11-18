# hotdocs

Spec-driven agentic development: the change-tracked assets are plain-text
specification documents, and the code and tests are generated from them by
a model and verified before they count. Human review shifts from reading
diffs of code to reading diffs of intent.

You write what a component must do and how to check it. `hotdocs generate`
has a model write the code and a test per acceptance criterion, then runs
those tests, mutation-tests them, and scans the result for licenses and
secrets. `hotdocs verify` says whether everything in a change is ready.
Python projects only.

## Try it

See `QUICKSTART.md`: install this checkout once, run `hotdocs init` in a
project, and generate the example component. The tool's own components stay
in this checkout; a project holds only its own (`D199`).

## How it works

```
specs/components/<name>/      you write this
  component.md                id, owners, the capability it realizes
  requirements/R-*.md         one MUST per file
  interface/library.md        exact signatures
  acceptance/AC-*.md          Given/When/Then with concrete values
  constraints.md

gen/<name>/                   the model writes this; never hand-edited
verification/<name>/          generated tests and the provenance manifest
```

`hotdocs lint` checks the corpus against `SPEC_GUIDELINES.md`. `hotdocs
generate comp-<name>` assembles the component's spec bundle, calls the
model, writes a test for each criterion, and records provenance only if
everything passes. `hotdocs verify` re-checks every component in a change,
read-only, and runs the product scenarios the change touches. A component
that fails is fixed by changing its spec and generating again, never by
editing `gen/`.

The everyday commands:

| Command | Does |
| --- | --- |
| `hotdocs init [--example]` | set up a project and choose a model provider |
| `hotdocs lint` | validate the spec corpus |
| `hotdocs generate comp-<name>` | generate and verify one component |
| `hotdocs verify [--changed=...]` | is everything ready |
| `hotdocs impact --changed=...` | blast radius of a spec change |
| `hotdocs assist --changed=...` | a model's review of a spec change |
| `hotdocs track feedback comp-<name>` | the last attempt's failing requirements |
| `hotdocs track ui build` | a readiness page for the corpus |
| `hotdocs corpus-graph build`, `docs-site build` | the corpus graph and a browsable site |

`hotdocs` with no arguments lists every verb.

## Status

This repository is the worked example: the tool is built from its own
specs. Every one of the 28 components under `specs/components/` is
generated from its spec on `claude-opus-5-5` and verified the same way a
project's are, each with a provenance manifest that `hotdocs verify` checks.
The hand-written versions that bootstrapped the chain (`generator`,
`llm-endpoint`, `spec-linter`, `graph-query-engine`, `cache-manager`) were
used to generate their own replacements, then swapped out once those passed.
`criterion-compiler` is generated too but stays sealed (`D206`): it lives in
`pipeline/` and is checked against hand-maintained characterization tests,
since trusting a compiled criterion means trusting its compiler.

`QUICKSTART.md` §6 lists the known limits of this release.
`notes/bootstrap-history.md` tells how each component first landed;
`verification/<slug>/BOOTSTRAP.md` has each one's full account.

Decisions are ADRs in `specs/decisions/`, `D1` through `D328` (`D1`–`D75`
from the 2026-10 baseline reset, the rest recorded as they were made).
`notes/initial-ideas.md` holds the original brainstorm, with its own
informal numbering.

## License

Apache-2.0 (`LICENSE`, `D202`). Generated code in your project is yours;
the license covers the tool.

## Repository layout

See `SPEC_GUIDELINES.md` for the enforceable rules. In brief:

| Path            | Purpose                                                        |
| --------------- | ------------------------------------------------------------- |
| `specs/`        | Normative specification documents: the source of truth.       |
| `gen/`          | Generated code. Not hand-edited (two declared exemptions only). |
| `pipeline/`     | The sealed `criterion-compiler`; frozen prompts live inline for now. |
| `verification/` | Generated tests, provenance manifests, `corpus-graph.json`.   |
| `tools/`        | The `hotdocs` entry point and hand-written maintenance scripts. |
| `examples/`     | The `slugify` project `hotdocs init --example` copies.        |
| `notes/`        | Design discussion and history. Non-normative.                 |
