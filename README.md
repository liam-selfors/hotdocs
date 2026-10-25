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

The rules are formalized (`SPEC_GUIDELINES.md`), and the repository's own
pipeline is itself the worked example: **20 components, fully specced**
under `specs/components/` (component anatomy, requirements, interfaces,
acceptance criteria, constraints — see `specs/architecture/
pipeline-decomposition.md` for the full decomposition), covering lint,
blast-radius analysis, generation, verification, compliance scanning,
provenance, merge-tracking, and a DuckDB-backed query layer shared across
several of them (`specs/architecture/graph-query-engine.md`).

`spec-linter` is the one component with a real, hand-bootstrapped
implementation (`gen/spec-linter/`) and a real passing test suite
(`verification/spec-linter/`) — standing in for the not-yet-built
generator/criterion-compiler pipeline, and the thing every spec change in
this repo is actually re-validated against before it's committed.
Everything else is fully specced but not yet generated: `pipeline/` (the
agent workflow that would do that generation) doesn't exist yet either.

Decisions are tracked as formal ADRs in `specs/decisions/` (`D15` onward);
`notes/initial-ideas.md` holds the original brainstorm (`D1`–`D14`,
informal) plus the full discussion behind every later decision.

## Repository conventions

See `SPEC_GUIDELINES.md` for the full, enforceable rules. Summary:

| Path            | Purpose                                                        |
| --------------- | ------------------------------------------------------------- |
| `specs/`        | Normative specification documents — the source of truth.      |
| `gen/`          | Generated code. Not hand-edited (two declared exemptions only). |
| `pipeline/`     | Agent workflow definitions, frozen prompts, model pins, toggles. |
| `verification/` | Generated tests, contract checks, drift detection, corpus graph. |
| `tools/`        | Hand-written repo-maintenance/authoring scripts. Not spec-driven, not gated. |
| `notes/`        | Brainstorming and design discussion. Non-normative.           |
