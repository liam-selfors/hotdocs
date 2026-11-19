---
id: arch-asset-kinds
title: Asset Kinds
status: draft
owners: [pipeline-team]
depends_on: []
---

# Asset Kinds

## Purpose

What a component may produce besides a Python package, and the one
contract every kind of asset meets so that generation, verification and
provenance work the same way for all of them (`D340`). Nothing
implements this document yet; it is the design the pipeline components
adopt one kind at a time. A project built with `hotdocs` defines its own
kinds through the same contract.

## Terms

- An **asset** is one generated file or directory a component produces:
  `gen/<slug>/<path>`.
- An **asset kind** names how an asset is laid out, checked, run and
  mutated. The kind `python` is today's behaviour, unchanged.
- A **kind definition** is a document,
  `specs/asset-kinds/<kind>.md`, plus an **adapter**, the code that
  carries out the definition.
- A component declares its assets in `component.md` frontmatter:

      assets:
        - {kind: python, path: docs_site_renderer/}
        - {kind: javascript, path: static/app.js}

  With no `assets` key, a component has the single asset
  `{kind: python, path: <module>/ or <module>.py}`, as today.

## The contract

A kind definition states each of the following. A definition that leaves
one out is a lint failure, not a default.

1. **Layout.** The files the generator must write for an asset of this
   kind, under `gen/<slug>/<path>`, and how a reply that writes others
   is rejected (`missing_module`, `malformed_layout`).
2. **Environment.** What an asset of this kind needs in order to run
   and be checked, and how `hotdocs` provisions it (see Environments
   below): the programs, each with a minimum version and the command
   that reports it (`node --version`, `python3 --version`), and the
   packages, read from a lockfile the project commits
   (`environments/<kind>/requirements.lock`, `package-lock.json`).
   When the environment cannot be provisioned, every criterion that
   needs it fails with `failure_origin` `"environment"` and the message
   `<kind> needs <program> <version>` or `<kind> environment: <reason>`;
   it is never skipped, because a skipped gate reads as a passing one.
3. **Surface.** What other assets and components may rely on: for code,
   its exported names; for data, its schema; for a document, its
   required sections and anchors. The adapter extracts the surface from
   a candidate, and the surface gate compares it with the interface.
4. **Running criteria.** pytest stays the one harness. A kind supplies
   a fixture, `asset_runner`, that a generated test uses to exercise
   the asset (run a script with arguments, call an exported function
   with JSON arguments and read JSON back, query a data file), and the
   text the test author is shown about using it. A test never shells
   out to the environment's programs itself.
5. **Strength check.** How the pipeline knows the tests would notice a
   wrong asset, the role mutation plays for Python. Exactly one of:
   - *mutation*: sites and swaps, stated as `mutation-runs.md` states
     Python's, with the same baseline and score rules;
   - *perturbation*: a fixed list of edits that make the asset wrong
     (drop a required section, change a stated value, break a
     reference, violate a schema rule), each of which must make some
     criterion fail;
   - *evaluation*: for text that drives a model, a fixed set of cases
     with expected judgements, scored as mutation is, against the bar.
6. **Test author guidance.** The text appended to every criterion
   bundle of a component that has this kind: how fixtures are built,
   what `asset_runner` returns, which mistakes a test must avoid. It is
   test-only text: it reaches test authors, never the generator.
7. **Generator guidance.** The text appended to the generator's bundle:
   conventions the asset must follow (module format, dialect, no
   network), never test mechanics.

## Environments

`hotdocs` itself always runs on Python, in its own environment. That
environment is the tool's, never an asset's: a project's assets run in
environments their kinds declare, and a project provisions only the
environments of kinds its components declare. A project whose
components declare only `javascript` assets needs Node and its
lockfile, and no Python packages of its own; one with no asset needing
Node never needs Node.

- **Where.** Each kind's environment lives in
  `<project>/.hotdocs/env/<kind>/` (a Python virtual environment, a
  `node_modules` directory), created by `hotdocs env sync` and on
  first use, and never committed. Its inputs are committed:
  `environments/<kind>/` holds the kind's lockfile.
- **What is recorded.** Provenance records, per asset, the kind, the
  environment's programs and versions as reported, and the SHA-256 of
  its lockfile. A changed lockfile changes the provenance key of every
  asset of that kind, as a changed dependency's code does today.
- **Isolation.** Criteria and strength runs for an asset use only its
  kind's environment: its interpreter or runtime, its packages, its
  `PATH` entries. They never see the tool's own packages, so a project
  asset cannot pass by importing something the project never declared.
- **The `python` kind.** A project's Python assets run in
  `.hotdocs/env/python/`, from `environments/python/requirements.lock`.
  The `hotdocs` corpus itself is the one exception, by declaration: its
  `python` environment is the tool's own (`requirements.txt`), because
  its components are the tool.

## Built-in kinds

| Kind | Layout | Environment | Surface | Strength |
| --- | --- | --- | --- | --- |
| `python` | `<module>.py` or `<module>/` | Python and the project's locked packages | Exported names | Mutation (`mutation-runs.md`) |
| `javascript` | One ES module file per asset, no imports outside the asset | Node >= 20 and the project's `package-lock.json` | `export` names | Mutation (`D335`'s tokens, applied to the whole file) |
| `sql` | One `.sql` file of named statements (`-- name: <name>` before each) | DuckDB (already a Python dependency) | Statement names and result columns | Mutation (comparison, `AND`/`OR`, `JOIN` type, `DISTINCT` dropped) |
| `data-schema` | A JSON Schema file plus example instances | Python `jsonschema` (a new dependency) | The schema itself | Perturbation (each schema keyword violated once) |
| `document` | Markdown with required sections | none | Section headings and anchors | Perturbation |
| `prompt` | Markdown prompt with named slots | the configured model | Slot names | Evaluation |

A built-in kind's definition ships with the tool under
`<tool_root>/specs/asset-kinds/`. Only `python` exists today; the
others are proposals, adopted in the order `notes/asset-kinds-survey.md`
gives.

## User-defined kinds

A project adds a kind by writing `specs/asset-kinds/<kind>.md` and its
adapter. The adapter is a component of the project like any other,
`comp-kind-<kind>`, whose interface is the adapter interface below, so
`hotdocs` generates and verifies it, and its provenance covers every
asset of that kind. A component with an asset of kind `<kind>` depends
on `comp-kind-<kind>`, so changing a kind regenerates exactly the
components that use it.

The adapter interface:

```
layout_errors(asset_dir: Path, declared: dict) -> list[str]
surface(asset_dir: Path, declared: dict) -> dict
environment() -> {"programs": [{"program", "min_version", "version_command"}], "lockfile": str | None}
provision(project_root: Path) -> dict  # {"ok", "reason", "versions", "lockfile_sha256"}
asset_runner(asset_dir: Path, declared: dict) -> callable
strength_sites(asset_dir: Path, declared: dict) -> list[Site]
apply_site(asset_dir: Path, site: Site) -> None
```

`strength_sites` and `apply_site` serve all three strength checks: a
site is a mutation, a perturbation or an evaluation case, and the score
is computed by `verifier-orchestrator` the same way for each.

A project kind may not weaken a gate: its definition is linted for the
seven parts, its adapter's own criteria must include one asset that its
strength check scores below the bar and one that passes, and a new
`spec-linter` rule fails a definition whose strength check is missing
or empty.

## Open questions

- Whether a built-in kind may be overridden by a project's kind of the
  same name (proposed: no; a project names its own variant).
- How `prompt` evaluation cases are kept from leaking into the prompt
  under test (proposed: they live under `verification/`, which the
  generator never sees, like generated tests).
- Whether `document` assets need an `llm-judge` part of their strength
  check for qualities perturbation cannot express.
