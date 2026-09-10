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

Early brainstorming. Nothing here is settled. See `notes/` for working ideas and
`specs/` (once it exists) for the real thing.

## Repository conventions (planned)

| Path            | Purpose                                                        |
| --------------- | ------------------------------------------------------------- |
| `specs/`        | Normative specification documents — the source of truth.      |
| `gen/`          | Generated code. Not hand-edited. Regenerable from `specs/`.   |
| `pipeline/`     | Agent workflow definitions, frozen prompts, model pins.       |
| `verification/` | Spec-derived test suites, contract checks, drift detection.   |
| `notes/`        | Brainstorming and design discussion. Non-normative.           |
