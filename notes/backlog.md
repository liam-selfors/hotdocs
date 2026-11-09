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
