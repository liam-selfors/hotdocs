# Quickstart

hotdocs turns written specs into verified code: you write what a
component must do and how to check it, `hotdocs generate` has a model write
the code and its tests, and `hotdocs verify` says whether everything is
ready. A component's code is Python; it can also declare files of other
kinds, such as a JavaScript module (section 5).

## 1. Install

You need Python 3.11 or newer and a model provider: the `claude` command
signed in, or an API key in an environment variable (Anthropic, OpenAI,
Gemini, any OpenAI-compatible server, or a local Ollama). Node 24 or
newer is needed only if a component declares a JavaScript asset.

From PyPI, as an isolated command-line tool:

```
pipx install hotdocs          # or: uv tool install hotdocs
```

With Homebrew, from the tap: `brew install <owner>/hotdocs/hotdocs`
(`packaging/homebrew/hotdocs.rb`). Either way the tool's own components
ship inside the package, read-only, and every project uses them from there.
This guide, `AUTHORING.md` and `agent-skills/` ship there too: `hotdocs
init` ends by printing this guide's path, and the other two sit beside it.

To work on hotdocs itself, install a checkout instead:

```
git clone <this repository> hotdocs && cd hotdocs
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

The editable install matters here: the tool's components are files in the
checkout, so `git pull` updates the tool for every project that uses this
environment. Keep it active in each project, or put its `bin/` on `PATH`.

Dependencies are pinned exactly in `requirements.txt`, which both installs
use and `hotdocs init` checks. `hotdocs lint` and the graph views load
DuckDB's `yaml` extension on first use, which needs network access once.

## 2. Create a project

```
mkdir myproject && cd myproject
hotdocs init --example
```

`init` creates `specs/`, `gen/` and `verification/`, records the tool
version in `.hotdocs-tool.json`, and asks which model provider to use
(`--provider claude-cli --yes` skips the questions). It tests the
connection, never asks for an API key, and stores only the *name* of the
environment variable that holds it in `hotdocs.toml`. `--example` adds a
tiny `slugify` component to start from.

Your `gen/` holds only your own components; the tool's stay in the tool, so
a component of yours may not reuse one of the tool's names (`hotdocs lint`
says so). `init` also writes an empty `.secret-allowlist.json`. To allow a
flagged string that is not a secret, add it to that file and record the
file's hash in a ratified decision (`allowlist_sha256` in its frontmatter):
the scanner honors a non-empty list only while its hash matches.

Run `init` again any time; it never overwrites. `hotdocs init --reconfigure`
changes only the provider.

Running `hotdocs` from inside a Claude Code session (an agent driving it)
with `claude-cli`: Claude Code sets `ANTHROPIC_API_KEY` for the commands
it starts, and that key does not work for a separate `claude -p` call.
Use your claude.ai login instead with `hotdocs init --provider claude-cli
--auth login`, or add `auth = "login"` to the `[llm]` table of
`hotdocs.toml`. Make the project a git repository: `hotdocs impact` and
`hotdocs assist` diff against its default branch (`origin/HEAD`'s target,
else `main`, else `master`).

## 3. Generate and verify

```
hotdocs lint                    # is the spec well-formed?
hotdocs generate comp-slugify   # model writes code and tests, then checks them
hotdocs verify                  # is everything ready?
```

`generate` writes `gen/slugify/` and `verification/slugify/`. Never edit
`gen/` by hand: change the spec and generate again.

`generate` makes up to three attempts: when a candidate fails, the next
attempt is told which requirement ids failed (never the tests
themselves). `--max-attempts=1` makes one. With `--mode=agentic` the model
instead works in a sandbox: it writes the module, imports it, writes and
runs its own tests, and revises before finishing. Agentic mode needs a
provider with tool use (`anthropic`, `openai`, `openai-compatible` or
`claude-cli`) and an OS sandbox (`sandbox-exec` on macOS, `bwrap` on
Linux); without one the model's code is not run unless you pass
`--allow-unisolated-exec`. Defaults can go in `hotdocs.toml`:

```
[generate]
max_attempts = 3
mode = "single"
```

Other commands you will reach for: `hotdocs spec check comp-slugify` (can
each criterion's test be written from what its author sees?),
`hotdocs impact --changed=comp-slugify` (what a spec change touches),
`hotdocs assist --changed=comp-slugify` (a model's review of the change:
lint findings, blast radius, a completeness score, overlaps),
`hotdocs decision new "<title>"` (record why), `hotdocs component new
<name>` (lay out a component), `hotdocs track ui build` (a readiness page)
and `hotdocs docs-site build` (a browsable site of the specs, written to
`dist/`). Those last two read `verification/corpus-graph.json`, so run
`hotdocs corpus-graph build` first, and again after the specs change.
Verbs that can use a model take the one in `hotdocs.toml`, saying so on
stderr; `--no-model` skips it. `hotdocs` alone lists every verb, and
`hotdocs <verb> --help` prints one verb's usage.

## 4. Write your own component

A component is a directory of small files, as in the example
(`specs/components/slugify/`):

- `component.md` — the id (`comp-<name>`), owners, and the capability it
  `realizes`;
- `requirements/R-<NAME>-001.md` — one requirement per file, each with
  `MUST`;
- `interface/library.md` — the exact function signatures;
- `acceptance/AC-<NAME>-001.md` — a `Covers:` line naming a requirement and
  a Given/When/Then with concrete values;
- `constraints.md`.

A component realizes a capability: what the product does for its user,
one file in `specs/product/`. Lay out both:

```
hotdocs capability new slugs          # specs/product/slugs.md, id P-SLUGS
hotdocs component new slugify --realizes=P-SLUGS
```

Without `--realizes`, `component new` writes `realizes: []`, which
`hotdocs lint` rejects. A finished capability file looks like the
example's `specs/product/slugs.md`:

```
---
id: P-SLUGS
title: Titles Become URL Slugs
status: draft
owners: [web-team]
---

# Titles Become URL Slugs

## Purpose

A page title can be turned into a URL-safe slug.

### CS-SLUGS-001
Covers: P-SLUGS
Kind: generated-test

(a Given/When/Then in a `gherkin` block, as in an acceptance criterion)
```

The scenario is optional. It is checked against the generated code of
every component that realizes the capability, so `hotdocs verify` runs it
only with a model.

Run `hotdocs lint` after every change, and `hotdocs spec check
comp-<name>` before generating. The most useful habit: state concrete
inputs and outputs in each acceptance criterion, and name every function the
code must provide. What you leave implicit, the model guesses.

Two rules matter most, because the model that writes the code never sees
the acceptance criteria, and the model that writes each criterion's test
sees only that criterion, its covered requirement and the interface:

- every behavior a criterion checks must also be stated in a requirement;
- every fact a test needs (a value, a file layout, an error) must be in the
  criterion, its requirement or the interface.

A component's docs are capped at 4,000 words and each file at 500.
`AUTHORING.md` covers all of this in depth: criterion kinds, writing
testable criteria, shared rules in `specs/architecture/`, decision
records, and when to split a component.

## 5. Other languages and files: asset kinds

A component's Python code is its implicit `python` asset. Anything else it
produces is declared in `component.md`'s frontmatter, one line, as
`<kind>:<path>` relative to the component's `gen/` directory:

```
assets: [javascript:static/app.js]
```

Every declared asset also needs an interface file,
`interface/assets/<file name>.md` (for `static/app.js`,
`interface/assets/app.js.md`), stating its surface in the kind's
notation. For `javascript` that is one export per line in a fenced block,
followed by what each function takes and returns:

```
export function filterNodes(nodes, query)
export function init(document)
```

Without that file every attempt fails the surface check, and `hotdocs
generate` reports `surface_check_failed` with the file it expected.

Each kind has a definition (`specs/architecture/asset-kind-<kind>.md`:
layout, environment, how criteria call it, how its tests are
strength-checked, and guidance for the model) and an adapter component,
`comp-kind-<kind>`, that the pipeline runs. The built-in kinds are
`python` and `javascript` (one ES module of pure functions over JSON
values, run in Node 24 or newer); their definitions are in the hotdocs
repository, not in a project. A criterion calls an exported function
through the `asset_runner` fixture, and its tests are mutation-tested on
the JavaScript itself. Never hide another language inside Python strings:
declare it as an asset. An undeclared kind fails `hotdocs lint`.

To add a kind, `hotdocs kind new <kind>` lays out its definition, its
adapter component and a draft decision; the `hotdocs-asset-kind` skill in
`agent-skills/` walks an agent through filling them in.

**The Python environment.** By default a project's code runs in the
environment `hotdocs` runs in. To give it its own, commit
`environments/python/requirements.lock` (it must pin `pytest`): `hotdocs`
builds `.hotdocs/env/python/` from it on first use, so the code cannot
import a package the project never declared. To require a Python version,
put a prefix such as `3.14` in `environments/python/python-version`.
Provenance records the Python version and a fingerprint of the installed
packages, so a component generated under one environment misses under
another, with the reason `environment differs`. `hotdocs generate` then
re-verifies the committed code first and regenerates only if that fails.

## 6. Reading a failure

`hotdocs generate` lists each attempt and, if none passed, ends with
`blocked` and a reason:

- `model_call_error` — no usable code was produced. A network, auth,
  rate-limit or timeout error is not retried: run it again later.
  `truncated_response` means the reply was cut off: raise the provider's
  output limit (below). For `empty_response` the message shows the start
  of what the model replied, which often names a detail the spec left
  out.
- `surface_check_failed` — the code did not import, used a name a
  dependency lacks, mishandled an unknown command-line argument, or an
  asset lacks an export its interface lists or has no interface file. A
  `surface:` line gives each finding.
- An environment failure (`javascript needs node >= 24`, `python
  environment: needs Python 3.14, found 3.12.4`) stops at once with no
  retry: fix the machine or the pin, then run it again.
- `test_authoring_failed` — code was produced but a criterion's test
  could not be written (a model call dropped twice): run it again;
  nothing shows the code wrong.
- `verification_failed` — a criterion failed on every attempt. The output
  names each failing criterion and why; a failure marked as the test's
  own means its test could not be written soundly. Nearly always the
  cause is in the spec: a missing detail, or an example that contradicts
  a requirement. Run `hotdocs spec check` on it and fix the spec; the
  next `generate` writes a fresh test for any criterion you changed.

`hotdocs track feedback comp-<name>` lists the failing requirement ids
from the last attempt, and `--retry-feedback=R-...` passes them to the
next `generate`.

A `mutation_error` line means every criterion passed, but the generated
tests failed (or hung) when rerun in the mutation sandbox, a temporary
copy of `gen/` whose working directory is not the repository root. A test
that reads files relative to the current directory is the usual cause.

`hotdocs verify` without `--model` reports every component and lists a
capability that needs a fresh run as `needs a fresh run; pass --model`.

## 7. Known limits

- The secret scan finds API keys, tokens and other high-entropy or
  provider-shaped strings, not ordinary passwords: a low-entropy value like
  `password = "hunter2"` passes. Keep passwords out of the repository.
- With the `claude-cli` provider, a large component's reply can outgrow
  the command's defaults and fail as `truncated_response`. Set
  `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000` and bound thinking with
  `MAX_THINKING_TOKENS` (the tool's own rebuild used `32000`).
- The live-provider tests are opt-in and cost real tokens:
  `HOTDOCS_LIVE=1 pytest verification/llm-endpoint/test_live_providers.py
  verification/llm-tool-endpoint/test_live_tool_loop.py
  verification/agentic-generator/test_live_slugify.py`.
- `hotdocs assist` and `hotdocs impact` need a git repository; without a
  default branch or a merge-base every file counts as changed.
- `hotdocs <verb> --help` prints the verb's summary and usage line, not a
  description of each flag; this guide and `AUTHORING.md` hold those.
- `license_scan not evaluated: no-reference-corpus` in `hotdocs
  generate`'s output is expected in a new project: the license scan
  compares generated code with a reference corpus of licensed code, and
  none is configured. It never blocks.
