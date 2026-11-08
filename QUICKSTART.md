# Quickstart

hotdocs turns written specs into verified Python code: you write what a
component must do and how to check it, `hotdocs generate` has a model write
the code and its tests, and `hotdocs verify` says whether everything is
ready. Python projects only.

## 1. Install

You need Python 3.10 or newer and a model provider: the `claude` command
signed in, or an API key in an environment variable (Anthropic, OpenAI,
Gemini, any OpenAI-compatible server, or a local Ollama).

```
git clone <this repository> hotdocs && cd hotdocs
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

The editable install matters: the tool's components are files in this
checkout, and every project uses them from here. Updating the checkout
(`git pull`) updates the tool for all your projects.

## 2. Create a project

```
mkdir myproject && cd myproject
hotdocs init --example
```

`init` creates `specs/`, `gen/` and `verification/`, records the tool
version in `.hotdocs-tool.json`, and asks which model provider to use. Your
`gen/` holds only your own components; the tool's stay in the tool, so a
component of yours may not reuse one of the tool's names (`hotdocs lint`
says so). It tests the connection, never asks for an API
key, and stores only the *name* of the environment variable that holds it in
`hotdocs.toml`. `--example` adds a tiny `slugify` component to start from. It also writes an
empty `.secret-allowlist.json`. To allow a flagged string that is not a
secret, add it to that file and record the file's hash in a ratified
decision (`allowlist_sha256` in its frontmatter): the scanner honors a
non-empty list only while its hash matches.
Run it again any time; it never overwrites. `hotdocs init --reconfigure`
changes only the provider.

## 3. Generate and verify

```
hotdocs lint                    # is the spec well-formed?
hotdocs generate comp-slugify   # model writes code and tests, then checks them
hotdocs verify                  # is everything ready?
```

`generate` writes `gen/slugify/` and `verification/slugify/`. Never edit
`gen/` by hand: change the spec and generate again.

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
no code was produced (the model or network failed): run it again.
`verification_failed` means code was produced and a criterion failed; the
output names each failing criterion and why. Nearly always the cause is in
the spec: a missing detail, or an example that contradicts a requirement.
Fix it there. `hotdocs track feedback comp-<name>` lists the failing
requirement ids from the last attempt, and `--retry-feedback=R-...` passes
them to the next `generate`.

## 6. Known limits

- The secret scan finds API keys, tokens and other high-entropy or
  provider-shaped strings, not ordinary passwords: a low-entropy value like
  `password = "hunter2"` passes. Keep passwords out of the repository.
- Five of the tool's own components (`generator`, `llm-endpoint`,
  `cache-manager`, `spec-linter`, `graph-query-engine`) are hand-written
  and tested, not generated from their specs; the rest are generated and
  verified like yours.
- `hotdocs review-packet build` does not yet find the tool's components
  from a project; it works only inside the tool's own checkout until it is
  regenerated.
- `hotdocs assist` and `hotdocs impact` need a git repository with a
  `main` or `master` branch.
