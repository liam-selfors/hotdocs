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
