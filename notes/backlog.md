# Backlog

Ideas and known gaps raised during design discussion but **not yet
decided** — distinct from `notes/initial-ideas.md` (the historical
brainstorm behind decisions already made) and `specs/decisions/` (ratified
ADRs). An entry here moves to a real `specs/decisions/D<N>.md` once
someone actually works through it; until then this is just the list of
things worth coming back to, so they don't get lost or silently dropped.
Once an entry is decided, the decision record holds its rationale and the
entry is removed here.

Nothing here is normative. Nothing here is implemented.

---

## `corpus-graph-builder`'s size status measures one dimension

`SPEC_GUIDELINES.md` §4 names eight sizing dimensions. `component_size`
(`D13`) measures `component_doc_words`, and `corpus-graph-builder`'s
`size_status` (`D200`) is defined on that one alone; `fan_out`/`fan_in`
are cheap graph properties `nodes`/`edges` already expose. But
`generated_code_loc`, `requirement_count`, `acceptance_count`,
`interface_surface` and `guarantee_count` have no named view, and
`spec-linter` writes no persistent, machine-readable findings artifact
(`hotdocs lint` only prints to stdout) for `corpus-graph-builder` to read
instead of recomputing. Adding a dimension means naming its view first,
the way `component_size` was settled, never re-deriving it per caller
(`SPEC_GUIDELINES.md` §10).

## From the authoring and agentic hardening round (2026-11)

- **`llm-endpoint` ignores `stop_reason`.** A single-shot reply cut off at
  `max_tokens` is now caught by the generator's END REPLY sentinel
  (`D304`), but `llm-endpoint` itself should report a `max_tokens` /
  `length` stop as its own error for every caller.
- **`llm-endpoint` forwards `temperature`.** Current Claude models reject
  sampling parameters with a 400; drop it for those models.
- **Tool use for `gemini` and `ollama`.** `llm-tool-endpoint` raises
  `ToolUseUnsupported` for both (`D308`).
- **`bwrap` is specified but untested.** The Linux OS sandbox for agentic
  mode (`specs/architecture/agent-sandbox.md`) has not run on Linux.
- **A tool-loop call log.** `llm-tool-endpoint` writes no
  `.hotdocs/calls/` records; `llm-endpoint`'s single-shot log does.
- **A whole-result grammar step.** `Then the result is <literal>` for
  `criterion-compiler`, so more criteria (the slugify example's among
  them) can be `compiled` rather than `generated-test`; deferred from
  this round (planned as `D306`).
- **Data-type references cascade widely.** `R-ASSEMBLE-013` pulls any
  data type an interface names, even in prose, into dependents' bundles;
  `ModelResponse.md`'s one mention of `GenerationResult` makes that
  schema reach 19 components. Consider resolving only types named in
  signatures or schema blocks.
- **`test-probe` passes a test that fails before the stub.** A test
  whose own setup raises, such as a `KeyError` from `str.format` over a
  template holding braces, reaches no code under test, yet
  `R-PROBE-005` gives it no finding. Such a failure, when no test in the
  file reached the stub, should be a `test_bug`. `D316`'s prompt rule
  covers the one case seen so far.

---

## A test's helpers named `test*` are collected by pytest

`D326` tells `verifier-orchestrator`'s test authors, through
`specs/architecture/verifier-fixtures.md`, never to name a helper with a
`test` prefix. The rule holds for every generated test and belongs in
`test-author`'s fixed prompt text (`D316`), or in its static checks
(`R-AUTHOR-020`) as a top-level `test*` function with parameters that
no fixture supplies. Either change regenerates `test-author` and its
dependents.

---

## The bootstrap dependency-surface gate misreads local names

`tools/bootstrap_component.py`'s dependency surface gate reported
"spec-bundle-assembler has no append" for a candidate whose local list
`assembler` called `.append`: it matches attribute uses by a name's
resemblance to a dependency, not by what the name is bound to. The
port into `surface-checker` (planned on `refine-authoring-agentic`)
should resolve names to the imports they come from.

---

## From the first walk through an installed package (2026-11-23)

Found by installing the `0.1.0` wheel and following `QUICKSTART.md` as a
new user would. `D359` and `D360` fixed the crash on a surface failure,
the version literal and the missing guides; `D361` made `hotdocs spec
check` report a declared asset with no interface file and stopped its
model layer asking which test framework to use. `D363`–`D366` gave
every verb a `--help`, added `hotdocs capability new`, put `/dist/` in
a new project's `.gitignore`, and made the two page builders name
`hotdocs corpus-graph build` when the graph is missing. These remain.

- **`hotdocs lint` does not look for a declared asset's interface
  file.** `interface/assets/<file name>.md` is required
  (`specs/architecture/asset-kinds.md`). `hotdocs spec check` reports a
  missing one (`D361`); a developer who skips it still learns only from
  `surface-checker`, after a generation. A lint rule beside `R-LINT-034`
  would catch it on every path; `spec-linter` is at the root of the hash
  tree, so it belongs in the next full wave.
- **A surface failure the spec causes is retried.** `generation-loop`
  retries every `surface_failed` attempt (`D310`), but a missing interface
  file, or an export the interface lists under a name the code may not
  use, fails the same way each time. `asset_error` findings whose cause
  is in the spec should end the loop like an environment failure.
- **A component's own `main` still answers `--help` with a usage
  error.** `hotdocs-cli` turns that answer into the verb's help (`D363`),
  so `hotdocs <verb> --help` works; `compile-criteria` alone answers
  `--help` itself. `specs/architecture/cli-conventions.md` should state
  that `--help` and `-h` print the usage line on stdout with exit code
  0; every CLI component implements that document (26 regenerations),
  so the change waits for a full wave.
- **Smaller.** Generated test files end without a newline.
  `hotdocs verify --no-model` describes a component never generated as
  needing a fresh run with a model, when it needs `hotdocs generate`.
  The built-in asset kinds' definitions ship in no installed package,
  so `QUICKSTART.md` can only point at the repository.

---

## Resolved entries

Removed from this file, with their rationale in the decision named:
the subagent-based model-call simulation (`D33`); a `context` property
for component structure (`D21`, `D22`); `GoldenScenarioReport.rationale`
(`D23`); the scanners' webhook failure path (`D26`); `failure_detail` on
compiled criteria (`D27`); `redundancy_flags`' shape (`D28`); the
`graph-query-engine` views and the lint rules built on them (`D13`); a
generating model guessing a dependency's import path (`D46` fixed the
layout rule to a flat module or top-level package, and `D199` plus each
component's `interface/library.md` now state the layout outright).
