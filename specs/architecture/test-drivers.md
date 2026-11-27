---
id: arch-test-drivers
title: Test Drivers
status: draft
owners: [pipeline-team]
depends_on: [arch-asset-kinds]
---

# Test Drivers

## Purpose

A program a component's tests use to exercise what the component
produces, when no plain pytest call can: a headless browser that loads
the page a component writes and acts on it as a user would (`D373`).
A driver is provisioned and recorded the way an asset kind's environment
is (`specs/architecture/asset-kinds.md`), but it produces nothing and is
never seen by the generator; it reaches only test authors and the tests
they write.

## Terms

- A **test driver** has a **definition**,
  `specs/architecture/test-driver-<name>.md`, and an **adapter**, the
  component `comp-driver-<name>`, the only part of a driver the running
  pipeline reads.
- A component declares the drivers its criteria use in `component.md`
  frontmatter, one line, read exactly as `assets` is:

      drivers: [browser]

  Each item is a driver name: lowercase letters, digits and `-`. No
  `drivers` line means none. A capability declares drivers the same way
  in its frontmatter, for its scenarios.
- When the project defines `<name>` itself (it has
  `specs/architecture/test-driver-<name>.md`), a component declaring it
  lists `comp-driver-<name>` in `depends_on`; a built-in driver's
  adapter is the tool's, and provenance covers it by hash.

## Lookup

As for asset kinds: `<repo_root>/gen/driver-<name>/driver_<module>.py`,
else `<tool_root>/gen/driver-<name>/driver_<module>.py`, `<module>`
being the name with each `-` replaced by `_`, loaded by path. Pipeline
components never list a driver adapter in `depends_on`, so adding or
changing a driver regenerates the driver and the components declaring
it, never the pipeline. A declared driver with neither a definition nor
an adapter is a lint failure (`R-LINT-036`); one with no adapter fails
verification of the declaring component with
`unknown test driver: <name>` (`R-RUNENV-003`).

## The definition

`specs/architecture/test-driver-<name>.md` has exactly these four
`## ` sections, each non-empty:

1. `## Environment` — the programs and packages the driver needs, each
   with a minimum version and the command that prints it, and the
   lockfile, if any, committed at `environments/driver-<name>/`.
2. `## Fixture` — the pytest fixture the driver supplies: its name, the
   object it yields, every method of that object, and what each returns
   or raises.
3. `## Isolation` — what the driven program may read, write and reach
   over the network, and the time limits.
4. `## Test author guidance` — what the adapter's `guidance()` returns
   as `"test_author"`, stated exactly, so the adapter's criteria pin it.

There is no generator guidance and no strength check: a driver makes
tests able to observe more, and the component's mutation score
(`specs/architecture/mutation-runs.md`) measures them as it measures
every test.

## The adapter interface

`comp-driver-<name>` provides a module `driver_<module>` with:

```
NAME: str
FIXTURE: str                               # the pytest fixture name
provision(repo_root: Path) -> dict         # {"ok", "reason", "versions", "lockfile_sha256"}
guidance() -> dict                         # {"test_author": str}
open_session(repo_root: Path, work_dir: Path) -> object
```

- `provision` never raises; it reports `ok` false with a `reason` of
  `<name> needs <program> >= <version>` or `<name> environment: <reason>`.
  `versions` and `lockfile_sha256` are as for an asset kind.
- `FIXTURE` equals `NAME` for every driver a project uses, so a test
  author's probe knows a driver's fixture from its name alone (`D385`).
- `open_session` returns the object the fixture yields, with a
  `close()` method the plugin calls at teardown even when the test
  fails. `work_dir` is a directory the session may write (pytest's
  `tmp_path` for the test).

## What each pipeline step does with a driver

- **Bundles.** `spec-bundle-assembler` appends to every
  `CriterionBundle`'s `testing` of a declaring component, after the
  asset kinds' texts, `\n## Test driver: <name>\n\n` followed by
  `guidance()["test_author"]`, stripped, for each declared driver in
  sorted order (`R-ASSEMBLE-017`). The `SpecBundle` never holds it: the
  generator writes the page, not the tests that drive it.
- **Environment.** `run-environment`'s `prepare` provisions each
  declared driver after the asset kinds (`R-RUNENV-003`). When one
  fails, every `generated-test` and `compiled` criterion of the
  component is `fail` with `failure_origin` `"environment"`, exactly as
  for an asset kind's environment (`R-VERIFY-020`).
- **Running criteria.** The plugin `specs/architecture/run-environment.md`
  defines gives each declared driver's fixture to every criterion,
  baseline and mutant run, and to a capability's scenario runs when the
  capability declares the driver (`prepare_capability`). A test using a
  fixture of a driver not declared errors at setup.
- **Probe.** `test-probe`'s stub run supplies each fixture named in
  `probe`'s `drivers` as an object whose every attribute access raises
  `HotdocsProbeStubReached`, so a test that reaches the driver reaches
  the code under test (`R-PROBE-009`).
- **Provenance.** `VerificationReport.drivers` lists each declared
  driver in sorted order, `{"name", "definition_sha256",
  "adapter_sha256", "versions", "lockfile_sha256"}`, hashed as
  `assets` entries are; `provenance-writer` copies it into the manifest
  and `provenance-checker`'s key includes it. A miss whose only
  differences are drivers' or assets' `versions` or `lockfile_sha256`
  is `environment differs` (`D345`), so a browser update re-verifies
  the committed code before anything is regenerated. A capability's
  scenario key includes its drivers' `versions` the same way.
- **Agentic generation.** The agent's `run_scratch_tests` gets no
  driver fixture (`specs/architecture/agent-sandbox.md`).

## Built-in drivers

| Driver | Fixture | Environment |
| --- | --- | --- |
| `browser` | `browser` | Playwright for Python with its Chromium (`test-driver-browser.md`) |

## Open questions

- Screenshots judged by a model with image input, for criteria about
  how a page looks: a criterion kind of its own, needing image input in
  `llm-endpoint`; proposed as the next decision.
- Comparing screenshots with approved baseline images: opt-in per
  criterion, each new baseline approved by a decision.
- A mutation site for wiring code (deleting one statement of a
  javascript asset's `init`), which today has none.
