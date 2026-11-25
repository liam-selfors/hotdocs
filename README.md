# hotdocs

Spec-driven agentic development: the change-tracked assets are plain-text
specification documents, and the code and tests are generated from them by
a model and verified before they count. Human review shifts from reading
diffs of code to reading diffs of intent.

You write what a component must do and how to check it. `hotdocs generate`
has a model write the code and a test per acceptance criterion, then runs
those tests, mutation-tests them, and scans the result for licenses and
secrets. `hotdocs verify` says whether everything in a change is ready.
Code is Python; a component can also declare files of other kinds, such as
a JavaScript module, each with its own definition and checks
(`specs/architecture/asset-kinds.md`).

## Try it

`pipx install --pip-args=--pre hotdocs` (or `uv tool install
--prerelease=allow hotdocs`, or `brew install
liam-selfors/hotdocs/hotdocs`), then see
`QUICKSTART.md`: run `hotdocs init --example` in a project and generate the
example component. The tool's own components ship inside the package; a
project holds only its own (`D199`, `D358`). `AUTHORING.md`
explains how to write specs that generate correctly the first time.

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
| `hotdocs spec check comp-<name>` | can each criterion's test be written from what its author sees? |
| `hotdocs generate comp-<name>` | generate and verify one component |
| `hotdocs verify [--changed=...]` | is everything ready |
| `hotdocs impact --changed=...` | blast radius of a spec change |
| `hotdocs assist --changed=...` | a model's review of a spec change |
| `hotdocs track feedback comp-<name>` | the last attempt's failing requirements |
| `hotdocs decision new "<title>"`, `capability new <name>`, `component new <name>`, `kind new <kind>` | scaffold a decision, a capability, a component or an asset kind |
| `hotdocs track ui build` | a readiness page for the corpus |
| `hotdocs corpus-graph build`, `docs-site build` | the corpus graph and a browsable site |

`hotdocs` with no arguments lists every verb.

## Status

hotdocs is alpha software: releases are pre-releases (`0.1.0a1` is the
first), and specs, commands and file formats may change between them.
Once a stable release exists, pip and uv skip pre-releases unless asked,
which is what the `--pre` and `--prerelease=allow` above do.

This repository is the worked example: the tool is built from its own
specs. Every one of the 37 components under `specs/components/` is
generated from its spec on `claude-opus-5-5` and verified the same way a
project's are, each with a provenance manifest that `hotdocs verify` checks.
The hand-written versions that bootstrapped the chain (`generator`,
`llm-endpoint`, `spec-linter`, `graph-query-engine`, `cache-manager`) were
used to generate their own replacements, then swapped out once those passed.
`criterion-compiler` is generated too but stays sealed (`D206`): it lives in
`pipeline/` and is checked against hand-maintained characterization tests,
since trusting a compiled criterion means trusting its compiler.

`QUICKSTART.md` §7 lists the known limits of this release.
`notes/bootstrap-history.md` tells how each component first landed;
`verification/<slug>/BOOTSTRAP.md` has each one's full account.

Decisions are ADRs in `specs/decisions/`, `D1` through `D372` (`D1`–`D75`
from the 2026-10 baseline reset, the rest recorded as they were made).
`notes/initial-ideas.md` holds the original brainstorm, with its own
informal numbering.

## Before pushing

Every commit pushed from this repository first passes
`tools/verify_push.py`: in a throwaway worktree of exactly that commit
it runs `hotdocs lint` and then `hotdocs verify`, which checks every
component's and capability's provenance without calling a model. Run
`python tools/verify_push.py --install-hook` once per clone to make it
the `pre-push` hook; `python tools/verify_push.py [<commit>]` runs it by
hand. Pull requests are reviewed and merged by a person.

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
