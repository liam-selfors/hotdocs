# Backlog

Ideas and known gaps raised during design discussion but **not yet
decided** — distinct from `notes/initial-ideas.md` (the historical
brainstorm behind decisions already made) and `specs/decisions/` (ratified
ADRs). An entry here moves to a real `specs/decisions/D<N>.md` once
someone actually works through it; until then this is just the list of
things worth coming back to, so they don't get lost or silently dropped.

Nothing here is normative. Nothing here is implemented.

---

## A generating model can guess a dependency's import path wrong (`D54`)

`SpecBundle.dependency_interfaces` (`R-ASSEMBLE-002`) gives a
dependency's public contract — names, signatures, fields — but never
says how that contract is organized into files or submodules, since no
component's `interface/` spec has ever needed to say so before two
independently-generated components actually needed to interoperate.
`generator`'s own self-regeneration attempt (`D54`) assumed
`cache-manager` was a package with a `.data` submodule; the real one is
a flat module — an import failure, caught before any acceptance
criterion was even attempted. Not resolved: either a corpus-wide
module-layout convention, or having `spec-bundle-assembler` expose a
dependency's actual public import path explicitly in the bundle. Will
matter more as more components are generated and start depending on
each other's generated code rather than hand-written code a human laid
out once.

---

~~**The subagent-based model-call simulation isn't reproducible from a
clean clone.**~~ **Resolved by `D47`.** The four `.claude/agents/*.md`
definitions (`generator`/`test-author`/`judge`/
`spec-completeness-assistant`) are deleted outright rather than fixed
in place — a real `gen/llm-endpoint/` implementation (dispatching via
the `claude` CLI's non-interactive mode, `D45`/`D46`) replaces the
mechanism entirely, and a fresh clone now has a real, working component
instead of a gap to reproduce. `generator`/`test-author`/
`spec-completeness-assistant`/the `judge` callable themselves remain
unimplemented — `D47` only builds the transport they'd dispatch
through. See `specs/decisions/D47.md`.

---

## ~~A `context` property for component structure~~ — resolved, `D34`/`D35`

Fully implemented: `component.md` gained a `Rationale` section so
`Purpose` stays dependent-safe (`D34`, `R-LINT-024`); a new
`component_context` view and `spec-bundle-assembler`'s
`dependency_context` field (`D35`, `R-ASSEMBLE-010`) now hand every
dependency's `Purpose` text to a generating model alongside its
`interface/` contract; `R-LINT-025` caps `Purpose`'s length
mechanically. See `specs/decisions/D34.md` and `specs/decisions/D35.md`
for the full record.

---

## ~~Four gaps found during the `D31`/`D32` corpus-wide audit~~ — all resolved, `D36`/`D38`

~~**`GoldenScenarioReport` has no `rationale` field.**~~ **Resolved by
`D36`.** Capability scenarios (renamed from "golden scenarios") can be
`llm-judge`-kind (`R-SCENARIO-001`), and `CapabilityScenarioReport` now
carries a per-scenario `rationale` field alongside `result`, mirroring
`VerificationReport.criteria[]`'s existing convention — plus the
report moved from one aggregate verdict per capability to one entry
per scenario, closing a second, deeper gap found during the same
analysis. See `specs/decisions/D36.md`.

~~**`license-scanner`/`secret-scanner`'s webhook notification has no
failure path.**~~ **Resolved by `D38`.** Both schemas gained a
`notification_delivery_error` field (`{category, message}` or `null`,
mirroring `model_call_error`'s shape) — `notified` keeps meaning
"was due," computed from preconditions alone; delivery outcome is this
separate field's job. The webhook call itself is now explicitly a
bounded, no-retry call, same posture `R-ENDPOINT-004` established for
model calls. See `specs/decisions/D38.md`.

~~**`compiled`-kind verification failures carry no underlying detail.**~~
**Resolved by `D38`.** `VerificationReport.criteria[]` gained
`failure_detail` (`{message, expected, actual}`, `R-VERIFY-012`) for a
failing `compiled`/`generated-test` criterion, mirroring `llm-judge`'s
`rationale` one `kind` family over. Deliberately excluded from
`requirement_results` and `retry_feedback`, preserving the existing
content boundaries. See `specs/decisions/D38.md`.

~~**`spec-completeness-assistant`'s `redundancy_flags` has no defined
shape.**~~ **Resolved by `D38`.** Defined as
`{new_requirement, overlaps_with, rationale}` (`R-ASSIST-005`), with
`rationale` mandatory on every populated entry — there is no
fired-but-unexplained state, since an entry exists only when a real
judgment call actually flagged one. See `specs/decisions/D38.md`.

---

## Three gaps found while settling `component_size` on DuckDB (`D42`)

~~**`graph-query-engine.md`'s `nodes`/`edges`/`component_docs` views
likely do not actually run.**~~ **Resolved by `D43`.** Confirmed and
fixed: `read_text(path, filename:=true)` errors (same bug
`component_size` had), present in `nodes` (four of seven branches),
`edges` (two branches), and `component_docs`. `read_yaml_frontmatter`'s
own `filename:=true` is a real, working parameter — only `read_text`
lacked it. A fourth, different bug surfaced in `component_context`
while fixing these: its `regexp_extract` needed the `'s'` (DOTALL) flag
to span a multi-line `Purpose` section, silently extracting an empty
string without it rather than erroring — the equivalent Python
(`_extract_purpose`) already had this right. All four views now run
against real DuckDB (`yaml`/`duckpgq` extensions both install and load
fine here) with every count cross-checked against an independent
file-system count. See `specs/decisions/D43.md`.

~~**`R-LINT-003`/`004`/`008`/`009`/`018`/`020`/`021` claim an
implementation that doesn't exist.**~~ **Resolved by `D44`.** All five
rules now actually query `graph-query-engine`'s shared `nodes`/`edges`
views (extracted as a real component in the same decision, out of
`graph-query-engine.md`'s previously-unverified embedded SQL) rather
than independently-written Python. Two residual native-Python checks
remain, each confirmed necessary by grep rather than assumed: an
`architecture`-doc `depends_on` check in `R-LINT-003`/`004` (the shared
views are component-scoped only), and `R-LINT-009`'s own line-number
reporting (the views don't map a `CS-id` back to its owning `product`
doc). Wiring this in also surfaced two new real bugs in
`graph-query-engine` itself — `read_yaml_frontmatter` raising on a
zero-match glob, and its struct-column auto-detection silently
dropping a field absent from every file in a glob at once — neither
reachable until a second, sparser caller (`spec-linter`'s own test
fixtures) actually exercised it. See `specs/decisions/D44.md`.

**`corpus-graph-builder`'s `R-GRAPH-003` has no defined mechanism for
six of the eight size-cap dimensions.** `component_size` (`D42`) now
covers `component_doc_words`; `fan_out`/`fan_in` are cheap graph
properties `nodes`/`edges` already expose. But `generated_code_loc`,
`requirement_count`, `acceptance_count`, `interface_surface`, and
`guarantee_count` have no named view, and `spec-linter` never writes a
persistent, machine-readable findings artifact (`hotdocs lint` only
prints to stdout) for `corpus-graph-builder` to read instead of
recomputing. Whenever `corpus-graph-builder` is actually implemented,
"size-vs-cap status" is exactly the kind of vague phrase that invites
re-deriving each dimension independently — the same trap
`component_size` just got caught in, before any code existed to catch
it in. Medium confidence — a real gap, but speculative until
`corpus-graph-builder` has real code to get this wrong in.
