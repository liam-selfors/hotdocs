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
contract every kind of asset meets, so that generation, verification and
provenance treat every kind alike (`D340`, `D343`). A project built with
`hotdocs` defines its own kinds through the same contract.

## Terms

- An **asset** is one generated file a component produces, at
  `gen/<slug>/<path>`.
- An **asset kind** names how an asset is laid out, run and checked.
  Every kind, `python` included (`D344`), has a **definition**, `specs/architecture/asset-kind-<kind>.md`, a spec that
  only people, lint and the adapter's own bundles read, and an
  **adapter**, the component `comp-kind-<kind>`, which carries the
  definition out and is the only part of a kind the running pipeline
  reads.
- Every component has one implicit `python` asset, its code directory
  `gen/<slug>/` (`specs/architecture/asset-kind-python.md`); it is never
  declared, and `python` in `assets` is a lint failure.
- A component declares its non-Python assets in `component.md`
  frontmatter as a list of `<kind>:<path>` strings:

      assets: [javascript:static/app.js]

  It is always one line. Every component reads it the same way: the
  text between `[` and `]` on the frontmatter line that starts with
  `assets:`, split on `,`, each item stripped and split at its first
  `:` into kind and path; no such line means no assets. A block-style
  list is a lint failure (`R-LINT-034`).
  `path` is relative to `gen/<slug>/`, uses `/`, has no `..`, does not
  end in `.py`, and names one file outside the component's Python
  module or package. With no `assets` key the component has only its
  Python module, as before. When the project defines `<kind>` itself
  (it has `specs/architecture/asset-kind-<kind>.md`), a component
  declaring it lists `comp-kind-<kind>` in `depends_on`; a built-in
  kind's adapter is the tool's, and provenance covers it by hash.

## Lookup

An adapter is loaded by path, never imported by name:
`<repo_root>/gen/kind-<kind>/kind_<kind>.py`, or, when that file does
not exist, `<tool_root>/gen/kind-<kind>/kind_<kind>.py`, the **tool
root** being the parent of the nearest directory named `gen` above the
reading module's own file. Pipeline components never list an adapter in
`depends_on`, so adding or changing a kind regenerates the kind and the
components that declare it, never the pipeline. The running pipeline
never reads a definition: everything it needs from a kind comes from
the adapter, so the tool's built-in kinds need nothing outside `gen/`.
A kind with neither a definition in the repository nor an adapter
(repository's or tool's) is a lint failure for every component
declaring it; a kind with no adapter fails generation and verification
of such a component with `unknown asset kind: <kind>`.

## The definition

`specs/architecture/asset-kind-<kind>.md` has exactly these seven `## ` sections,
each non-empty; one missing or empty is a lint failure.

1. `## Layout` — what the file at `path` must be, and how a reply that
   writes something else is rejected.
2. `## Environment` — the programs the kind needs, each with a minimum
   version and the command that prints its version, and the lockfile,
   if any, committed at `environments/<kind>/`.
3. `## Surface` — what a consumer may rely on, and its notation in the
   asset's interface file.
4. `## Running criteria` — what `asset_runner` takes and returns.
5. `## Strength check` — exactly one of *mutation* (sites and swaps,
   stated as `mutation-runs.md` states Python's), *perturbation* (a
   fixed list of edits that make the asset wrong) or *evaluation* (fixed
   cases with expected judgements, for text that drives a model).
6. `## Test author guidance` — what the adapter's `guidance()` returns
   as `"test_author"`: test-only text, how a test builds fixtures and
   calls `asset_runner`, and what it must not do.
7. `## Generator guidance` — what `guidance()` returns as `"generator"`:
   conventions the asset must follow, never test mechanics.

A definition states the two guidance texts exactly, so the adapter's
criteria pin them; a later decision may state requirements on them
instead, verified by evaluation, regenerating only the adapter.

## What each pipeline step does with an asset

- **Interface.** Each asset has `interface/assets/<file name>.md` (for
  `static/app.js`, `interface/assets/app.js.md`) stating its surface in
  the kind's notation. It is interface text: both the generator and
  every test author see it.
- **Bundles.** `spec-bundle-assembler` appends to the `SpecBundle`, for
  each declared kind in sorted order, `## Asset kind: <kind>` followed by
  the adapter's `guidance()["generator"]`; and to every
  `CriterionBundle`'s `testing`, after any `Uses:` documents,
  `\n## Asset kind: <kind>\n\n` followed by `guidance()["test_author"]`,
  each text stripped. Neither text reaches the other side.
- **Layout.** First, each kind, the implicit `python` first and then
  each declared kind, with no adapter, or whose
  `provision(repo_root)` reports `ok` false, ends generation with the
  category `environment`, before any model call, and the message `unknown asset kind: <kind>` or
  the adapter's `reason`; no model call can fix it, so it is never
  retried. Then a reply MUST write every declared asset path, besides the
  Python module; a declared path left unwritten is `missing_asset`.
  Writing an undeclared non-`.py` file is `malformed_layout`. The reply's
  `.py` files, as one code directory, and then each written asset are
  checked with their adapter's `layout_errors`; any error is
  `malformed_layout` with the adapter's messages.
- **Surface.** After `provision` reports `ok` (a failure is a finding
  with its `reason`), `surface-checker` compares `surface(...)["names"]` with
  the names the asset's interface file states; a name stated and not
  provided is a surface failure, as for a missing Python name. For
  `python`, `surface-checker`'s import and dependency checks are the
  surface gate (`asset-kind-python.md`).
- **Running criteria.** Every criterion run and mutation run gets the
  pytest fixture `asset_runner`, from a plugin `verifier-orchestrator`
  supplies with `-p`. `asset_runner(path)` returns the adapter's
  callable for the declared asset at `path` in the code being verified;
  a path not declared raises `KeyError`. Generated tests stay plain
  pytest and never run the environment's programs themselves. Every
  pytest run of a component, criterion, baseline or mutant, uses the
  `interpreter` the `python` adapter's `provision` reports.
- **Probe.** `test-probe`'s stub run supplies an `asset_runner` fixture
  whose callable raises `HotdocsProbeStubReached` when called, so a test
  that reaches an asset reaches the code under test.
- **Retries.** `missing_asset` and `malformed_layout` are retried by
  `generation-loop` as `missing_module` is.
- **Environment.** Before a component's criteria run,
  `verifier-orchestrator` calls `provision(repo_root)` for the implicit
  `python` kind and then each declared kind. When it reports `ok` false,
  every `generated-test` and `compiled` criterion of the component, each
  of which runs its code, is `fail` with `failure_origin` `"environment"` and
  `failure_detail.message` the adapter's `reason`, the mutation score is
  null, and nothing is run or skipped silently.
- **Strength.** The mutation score covers every asset: the `python`
  adapter's `strength_sites(<copy>)` over the code directory's copy, then
  each declared asset's `strength_sites(...)` in declaration order, each applied alone with
  `apply_site` in the mutation sandbox, killed exactly as a Python
  mutant is. One score for the component, against the same bar.
- **Language outside an asset.** A `str` constant of a component's
  Python code, never a docstring, that is at least 200 characters long,
  matches `\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s` and contains `;`
  or `{`, holds JavaScript no mutation reaches. Verification reports
  `mutation_score` null and `mutation_error`
  `javascript in a string at <file>:<line>; declare it as an asset (specs/architecture/asset-kinds.md)`
  with `<file>` relative to `gen/<slug>/`, so the component fails rather
  than report a score its logic never earned (issue #13).
- **Provenance.** `VerificationReport.assets` lists the implicit
  `python` asset first, with `path` `"."`, then each declared asset in
  declaration order,
  `{"kind", "path", "definition_sha256", "adapter_sha256", "versions", "lockfile_sha256"}`:
  the SHA-256 of `<repo_root>/specs/architecture/asset-kind-<kind>.md`
  (null when the repository does not define the kind) and of the adapter
  module as Lookup finds it, and `versions` and `lockfile_sha256` as `provision`
  reported them. Every hash is
  `"sha256:"` followed by the lowercase hex SHA-256 of the file's raw
  bytes, as `spec_bundle_hash` is written, and `provision` is called
  once per distinct kind.
  `provenance-writer` copies it into the manifest's `assets` and
  `provenance-checker`'s key includes it, so a changed definition,
  adapter, program version or lockfile makes the component miss.

## The adapter interface

`comp-kind-<kind>` provides a module `kind_<kind>` with:

```
KIND: str
layout_errors(asset_file: Path) -> list[str]
surface(asset_file: Path) -> dict          # {"names": [str, ...]}
provision(repo_root: Path) -> dict         # {"ok", "reason", "versions", "lockfile_sha256", "interpreter"}
guidance() -> dict                         # {"generator": str, "test_author": str}
asset_runner(asset_file: Path) -> Callable[[str, list], object]
strength_sites(asset_file: Path) -> list[dict]   # each has "description"
apply_site(asset_file: Path, site: dict) -> None
```

- `asset_file` is the asset in the code being checked: a candidate's,
  the mutation sandbox's or the committed one.
- `provision` never raises: it reports `ok` false with a `reason` of
  `<kind> needs <program> >= <version>` or `<kind> environment: <reason>`.
  `versions` maps each program to the version it printed;
  `lockfile_sha256` is `"sha256:<hex>"` of the lockfile's bytes, or null
  with no lockfile; `interpreter` is the absolute path of the Python that
  runs the component's tests for `python`, and null for every other
  kind.
- The callable `asset_runner` returns takes an entry point and a list of
  JSON values and returns a JSON value, raising `AssetError` (defined by
  the adapter, with the asset's own error message) when the asset
  raises. It runs with the kind's environment only, never `hotdocs`'
  own packages, with no network, and gives up after 30 seconds with
  `AssetError("timed out after 30 seconds")`.
- `strength_sites` lists every site in a fixed order; `apply_site`
  rewrites `asset_file` with that one change.

An adapter's own criteria include a calibration pair: one asset with a
suite its strength check scores at or above the bar, and one whose weak
suite scores below it. A strength check that cannot fail is a defect.

## Environments

`hotdocs` runs in its own Python environment. A kind's environment lives in `<repo_root>/.hotdocs/env/<kind>/`, never
committed, built from its committed lockfile by the adapter's
`provision` on first use; a project provisions only the environments of the kinds
its components declare, so a project with no `javascript` asset never
needs Node. The `python` kind runs in `.hotdocs/env/python/`, built
from `environments/python/requirements.lock`, when the project commits
that lock, so its code cannot import a package the project never
declared (`D340`, `D344`); without a lock it runs in `hotdocs`' own
environment, as the `hotdocs` corpus itself does.

## Built-in kinds

| Kind | Asset | Environment | Surface | Strength |
| --- | --- | --- | --- | --- |
| `python` | The code directory, implicit | Python; a project lock optional | Public names; `surface-checker`'s checks | Mutation |
| `javascript` | One ES module file | Node >= 24 | Exported names | Mutation |

Proposed next, each its own decision and adapter: `sql`, `data-schema`,
`sandbox-profile`, `document`, `prompt` (`notes/asset-kinds-survey.md`).

## Open questions

- Whether a project kind may shadow a built-in kind of the same name
  (today: yes, the project's definition and adapter are found first).
- How `prompt` evaluation cases are kept from the prompt under test
  (proposed: under `verification/`, like generated tests).
