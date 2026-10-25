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

## Four gaps found during the `D31`/`D32` corpus-wide audit, not yet acted on

~~**`GoldenScenarioReport` has no `rationale` field.**~~ **Resolved by
`D36`.** Capability scenarios (renamed from "golden scenarios") can be
`llm-judge`-kind (`R-SCENARIO-001`), and `CapabilityScenarioReport` now
carries a per-scenario `rationale` field alongside `result`, mirroring
`VerificationReport.criteria[]`'s existing convention — plus the
report moved from one aggregate verdict per capability to one entry
per scenario, closing a second, deeper gap found during the same
analysis. See `specs/decisions/D36.md`.

**`license-scanner`/`secret-scanner`'s webhook notification has no
failure path.** `R-LICENSE-003`/`R-SECRET-004` specify precisely when a
notification to `VAR-COMPLIANCE-WEBHOOK-URL` must fire, but neither
schema (`LicenseScanResult`/`SecretScanResult`'s `notified` field) can
distinguish "notification was due and delivered" from "notification was
due and the webhook call itself failed" — a real HTTP call with the same
network/auth/timeout failure modes this corpus is otherwise careful
about everywhere else. High confidence.

**`compiled`-kind verification failures carry no underlying detail.**
`VerificationReport.criteria[].result` is just `pass`/`fail`/`skipped`
for a `compiled` criterion — no slot for which assertion failed or
expected-vs-actual, unlike the `rationale` field already carved out for
`llm-judge` results. Medium confidence — "this is just normal
test-runner output, out of scope for a structured report" is a
plausible, just-never-stated justification.

**`spec-completeness-assistant`'s `redundancy_flags` has no defined
shape.** `CompletenessReport.md` shows `"redundancy_flags": []` with no
example of a populated entry, even though `R-ASSIST-005` describes this
as exactly the kind of judgment call that should carry a rationale.
Medium confidence — may be under-specified rather than demonstrably
wrong.
