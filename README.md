# hotdocs

An experiment in **spec-driven agentic development**: a way of building software
where the primary change-tracked assets are plain-text specification documents,
and code, tests, and configuration are regenerated from those specs by coding
agents running in a CI/CD pipeline.

The bet: if the specification corpus is structured strictly enough and its
acceptance criteria are strong enough, we can trust an automated pipeline to
produce the code — and human review can shift from reviewing diffs of code to
reviewing diffs of intent.

## Status

Brainstorming is done (`notes/initial-ideas.md`, decisions D1–D14), the rules
are formalized (`SPEC_GUIDELINES.md`), and the repository scaffold exists.
Nothing under `specs/`, `gen/`, `pipeline/`, or `verification/` has real
content yet — no components, no linter, no generation pipeline. Next up: a
small example project to stress-test the design against something concrete.

## Repository conventions

See `SPEC_GUIDELINES.md` for the full, enforceable rules. Summary:

| Path            | Purpose                                                        |
| --------------- | ------------------------------------------------------------- |
| `specs/`        | Normative specification documents — the source of truth.      |
| `gen/`          | Generated code. Not hand-edited (two declared exemptions only). |
| `pipeline/`     | Agent workflow definitions, frozen prompts, model pins, toggles. |
| `verification/` | Generated tests, contract checks, drift detection, corpus graph. |
| `notes/`        | Brainstorming and design discussion. Non-normative.           |
