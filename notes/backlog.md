# Backlog

Ideas and known gaps raised during design discussion but **not yet
decided** — distinct from `notes/initial-ideas.md` (the historical
brainstorm behind decisions already made) and `specs/decisions/` (ratified
ADRs). An entry here moves to a real `specs/decisions/D<N>.md` once
someone actually works through it; until then this is just the list of
things worth coming back to, so they don't get lost or silently dropped.

Nothing here is normative. Nothing here is implemented.

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

## Three gaps found while settling `component_size` on DuckDB (`D42`), not yet acted on

**`graph-query-engine.md`'s `nodes`/`edges`/`component_docs` views
likely do not actually run.** Confirmed for `nodes` and the `read_text`
half of `component_docs` by actually executing the SQL against real
DuckDB (2.0.0): `read_text(path, filename:=true)` errors —
`filename:=true` is a `read_json`/`read_csv` keyword, not `read_text`'s,
which already returns a `filename` column unconditionally. Nine of
`graph-query-engine.md`'s fourteen `filename:=true` occurrences call
`read_text`; the `nodes` view alone uses it in three of its seven
branches (guarantee/requirement/acceptance node kinds) plus the
`capability_scenario` branch, so the view as specified cannot be
created at all. The other four occurrences (`read_json`, confirmed
fine) and four more (`read_yaml_frontmatter`, an extension function
not verified here — not installed) weren't checked. This was never
caught because nothing has ever actually executed any of this SQL —
see the next item. High confidence on the `read_text` calls
specifically (empirically confirmed, same bug `component_size` had);
unverified on `read_yaml_frontmatter`.

**`R-LINT-003`/`004`/`008`/`009`/`018`/`020`/`021` claim an
implementation that doesn't exist.** All seven state (`R-LINT-020`/
`021` explicitly, the other five by being the rules those two govern)
that reference resolution, acyclicity, `depends_on_guarantees`
resolution, and both traceability directions are "implemented as
queries over the `nodes`/`edges` views." `gen/spec-linter/
spec_linter.py` contains zero references to `duckdb` outside the new
`_component_doc_words` lookup (`D42`) — `rule_reference_resolution`,
`rule_acyclic_graph`, and the rest are plain Python over
`corpus.id_index`/`corpus.frontmatter`, logically equivalent but never
actually running the SQL the requirements describe. `BOOTSTRAP.md`
was never updated to document this gap when `R-LINT-020`/`021` were
added (`D24`/`D27`) — its own "requirements added after D15" section
stops at `R-LINT-019`. High confidence; confirmed by reading the real
code, not inferred.

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
