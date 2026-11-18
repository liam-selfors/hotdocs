# Quickstart

hotdocs turns written specs into verified Python code: you write what a
component must do and how to check it, `hotdocs generate` has a model write
the code and its tests, and `hotdocs verify` says whether everything is
ready. Python projects only.

## 1. Install

You need Python 3.11 or newer and a model provider: the `claude` command
signed in, or an API key in an environment variable (Anthropic, OpenAI,
Gemini, any OpenAI-compatible server, or a local Ollama).

```
git clone <this repository> hotdocs && cd hotdocs
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

This is the one environment hotdocs uses. The editable install matters:
the tool's components are files in this checkout, and every project uses
them from here. Updating the checkout (`git pull`) updates the tool for all
your projects. Keep this environment active in every project (or put its
`bin/` on `PATH`); a project has no environment of its own. Dependencies
are pinned in `requirements.txt`, the list `pip install -e .` installs and
`hotdocs init` checks.

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
`hotdocs.toml`. Make the project a git repository with a `main`
branch: `hotdocs impact` and `hotdocs assist` diff against it.

## 3. Generate and verify

```
hotdocs lint                    # is the spec well-formed?
hotdocs generate comp-slugify   # model writes code and tests, then checks them
hotdocs verify                  # is everything ready?
```

`generate` writes `gen/slugify/` and `verification/slugify/`. Never edit
`gen/` by hand: change the spec and generate again.

Other commands you will reach for: `hotdocs impact --changed=comp-slugify`
(what a spec change touches), `hotdocs assist --changed=comp-slugify
--model=...` (a model's review of the change: lint findings, blast radius,
a completeness score), `hotdocs track ui build` (a readiness page) and
`hotdocs docs-site build` (a browsable site of the specs). `hotdocs` alone
lists every verb.

## 4. Write your own component

A component is a directory of small files, as in the example
(`specs/components/slugify/`):

- `component.md` — the id (`comp-<name>`), owners, and the capability it
  `realizes` (declared in `specs/product/`);
- `requirements/R-<NAME>-001.md` — one requirement per file, each with
  `MUST`;
- `interface/library.md` — the exact function signatures;
- `acceptance/AC-<NAME>-001.md` — a `Covers:` line naming a requirement and
  a Given/When/Then with concrete values;
- `constraints.md`.

Run `hotdocs lint` after every change. The most useful habit: state concrete
inputs and outputs in each acceptance criterion, and name every function the
code must provide. What you leave implicit, the model guesses.

## 5. Reading a failure

`hotdocs generate` ends with `blocked` and a reason. `model_call_error` means
no code was produced (the model or network failed): run it again. For
`empty_response` the message shows the start of what the model replied,
which often names a detail the spec left out. `test_authoring_failed`
means code was produced but a criterion's test could not be written (a
model call dropped twice): run it again; nothing shows the code wrong.
`verification_failed` means code was produced and a criterion failed; the
output names each failing criterion and why. Nearly always the cause is in
the spec: a missing detail, or an example that contradicts a requirement.
Fix it there; the next `generate` writes a fresh test for any criterion
you changed. `hotdocs track feedback comp-<name>` lists the failing
requirement ids from the last attempt, and `--retry-feedback=R-...` passes
them to the next `generate`.

A `mutation_error` line means every criterion passed, but the generated
tests failed (or hung) when rerun in the mutation sandbox, a temporary
copy of `gen/` whose working directory is not the repository root. A test
that reads files relative to the current directory is the usual cause.

`hotdocs verify` without `--model` reports every component and lists a
capability that needs a fresh run as `needs a fresh run; pass --model`.

## 6. Known limits

- The secret scan finds API keys, tokens and other high-entropy or
  provider-shaped strings, not ordinary passwords: a low-entropy value like
  `password = "hunter2"` passes. Keep passwords out of the repository.
- With the `claude-cli` provider, a large component's reply can outgrow
  the command's defaults. Set `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000` and
  bound thinking with `MAX_THINKING_TOKENS` (the tool's own rebuild used
  `32000`) so the whole reply fits: a file the reply cuts off before its
  end marker is dropped, and verification then fails for its absence.
- `hotdocs assist` and `hotdocs impact` need a git repository with a
  `main` or `master` branch.
