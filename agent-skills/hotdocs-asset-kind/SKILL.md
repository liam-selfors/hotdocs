---
name: hotdocs-asset-kind
description: Define a new hotdocs asset kind (a non-Python artifact type such as JavaScript, SQL, a data schema, a document or a prompt) for a project built with hotdocs, or move an existing component's embedded non-Python text into a declared asset. Use when the user wants a component to produce something other than a Python package, asks how hotdocs can spec another language or file type, or a component holds another language inside Python strings.
---

# Defining a hotdocs asset kind

The contract is `specs/architecture/asset-kinds.md`. Read it first, every
time; this skill is the procedure for meeting it, not a substitute. It
ships with the tool, not in a project: look under the directory that
holds the tool's `QUICKSTART.md` (`hotdocs init` prints that path), where
the built-in kinds' definitions, `asset-kind-python.md` and
`asset-kind-javascript.md`, sit beside it as worked examples. A
kind is only useful if its gates are as strict as Python's, so most of
this procedure is about the strength check and the test-only text, where
past failures came from.

## 1. Establish the asset before writing anything

Ask the user, or find in the code, and write down:

- What the asset is, concretely: one file or several, its language or
  format, and one real example from this project.
- Who consumes it: another component, a browser, a database, a model, a
  human reader. The consumer decides the surface.
- What would make it wrong in a way that matters. List at least five
  concrete wrong versions. If you cannot, the strength check will be
  weak; stop and work this out with the user.
- What must be installed to run or check it, with versions.

Check `<tool_root>/gen/kind-*/` for a built-in kind (an adapter) that
already fits. Prefer extending a built-in kind's declaration over a new kind.

Decisions that are the user's, not yours: adding an environment (a
program or package set) the project does not already need; choosing evaluation (model calls on every
verification) as a strength check; anything that makes a gate skip
instead of fail.

## 2. Write the definition, strength check first

Create `specs/architecture/asset-kind-<kind>.md` with the seven parts the contract
lists. Write them in this order:

1. **Strength check.** Pick mutation for executable code, perturbation
   for documents, data and templates, evaluation only for text that
   drives a model. List every site or perturbation explicitly. Each of
   the wrong versions from step 1 must correspond to at least one site.
2. **Surface.** Exactly what a consumer relies on, extractable by code
   without judgement.
3. **Running criteria.** What `asset_runner` takes and returns, with one
   example call and result. Inputs and outputs are JSON-shaped, so
   tests stay plain pytest.
4. **Layout**, **environment** (programs with versions, the lockfile,
   and how `provision` reports failure), then the two guidance texts.
   Never rely on packages from `hotdocs`' own environment.

## 3. Keep test text and generator text apart

- Test author guidance holds fixture mechanics only: how to build a
  fixture, how to call `asset_runner`, where files go. Never restate a
  requirement; tests check requirements, not a paraphrase.
- Generator guidance holds conventions the asset must follow. Never
  test mechanics.
- Shapes the asset itself reads (an input file's format, a schema it
  validates against) are interface text, visible to both.

## 4. Close the gaps that broke tests before

Every rule a test needs must be written down; a test author that has to
guess will guess differently on each run. Check the definition states:

- Where every fixture file lives, relative to what, and how a test
  finds any real file it copies. Never "from the live repository" or
  the current directory: verification and mutation runs use different
  directories (`D324`, `D336`, `D339`).
- The exact text or JSON of any reply, message or error a test asserts.
- What a test must not do: shell out to the environment's programs directly, depend
  on wall-clock time or network, define top-level `test*` helpers.
- How a fake or stand-in is installed, if tests need one.

## 5. Build and calibrate the adapter

1. Write `comp-kind-<kind>`'s spec with the adapter interface from the
   contract, and acceptance criteria that include two calibration
   assets: a correct one whose suite scores at or above the bar, and a
   deliberately weak suite that scores below it. A strength check that
   cannot fail is a defect.
2. Add a draft decision recording the kind and why it is needed
   (`hotdocs decision new`).
3. Run `hotdocs lint`, then `hotdocs spec check` on the kind's
   component, and resolve every finding.
4. Generate the adapter with `hotdocs generate comp-kind-<kind>`; it
   must land with provenance like any component.
5. Declare the asset on one consuming component, regenerate it, and
   confirm its verification report shows a strength score computed by
   the new kind, not by Python's mutation.

## 6. Report

Tell the user: the kind and its seven parts in one paragraph each, the
calibration scores, every environment it adds, the decision id, and what
you left open. Never report a kind as done while its strength check is
untested.

## Worked example: `javascript`

- Asset: `static/app.js` in `docs-site-renderer`, an ES module whose
  pure functions (`filterNodes(snapshot, query)`, `neighbors(graph,
  id)`) take and return JSON, plus a thin DOM layer that wires them to
  clicks.
- Wrong versions: a filter that ignores case, a search that misses
  partial matches, a neighbor list that includes the node itself, an
  off-by-one on depth, a click handler bound to the wrong element.
- Strength: mutation, `D335`'s token swaps over the whole file. The DOM
  layer stays thin and is checked through the rendered HTML; the
  pure functions carry the behaviour and the mutants.
- Running: `asset_runner("filterNodes", [snapshot, "gen"])` runs
  `node --input-type=module` on a fixed driver that imports the module
  and prints the JSON result.
- Environment: Node >= 20 and the project's `package-lock.json`,
  provisioned only for projects that declare a `javascript` asset.
