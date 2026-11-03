# Quickstart

> **Status:** steps 1 and 4 were run as written. Steps 2, 3, 5 and 6 follow
> the `hotdocs-cli` component's spec and had **not** been run end to end when
> this was written, because the model backend hit its usage limit
> mid-build. Delete this note once `hotdocs init --example`, `lint`,
> `generate comp-slugify` and `verify` have been run from a fresh install.

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
checkout, which `hotdocs init` copies into each project.

## 2. Create a project

```
mkdir myproject && cd myproject
hotdocs init --example
```

`init` creates `specs/`, `gen/`, `verification/`, `pipeline/`, copies the
tool into `gen/` and `pipeline/` (recorded in `.hotdocs-tool.json`), and asks
which model provider to use. It tests the connection, never asks for an API
key, and stores only the *name* of the environment variable that holds it in
`hotdocs.toml`. `--example` adds a tiny `slugify` component to start from.
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

## 6. Known issues

- `hotdocs lint` fails on a project with no components yet, so start from
  `--example` or add a component first.
