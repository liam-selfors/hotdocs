# Backlog

Ideas and known gaps raised during design discussion but **not yet
decided** — distinct from `notes/initial-ideas.md` (the historical
brainstorm behind decisions already made) and `specs/decisions/` (ratified
ADRs). An entry here moves to a real `specs/decisions/D<N>.md` once
someone actually works through it; until then this is just the list of
things worth coming back to, so they don't get lost or silently dropped.

Nothing here is normative. Nothing here is implemented.

---

## A `context` property for component structure

**Raised:** alongside the `D31`–`D33` retry-feedback work.

**The idea:** a compiled, concise, outward-facing description of a
component — what it does and why, not just its raw contract — that
*dependents* reference instead of (or alongside) the raw `interface/`
files they currently get.

**Why this might be a real gap, not just a nice-to-have:**
`spec-bundle-assembler`'s `SpecBundle.dependency_interfaces` currently
hands a generating model only the dependency's raw `interface/` file
content (`<bar/interface/ content>` — see `SpecBundle.md`) — cli.md's
syntax, library.md's signatures, data/'s schemas. It never includes any
part of the dependency's own `component.md` `Purpose`/`Scope` prose. A
model generating `comp-foo`, which depends on `comp-bar`, currently sees
*what* it can call on `comp-bar` and the exact shape of the call, but
never *why* `comp-bar` exists or what it's actually for. That's a
plausible real risk: a call that's type-correct per the signature but
wrong per an intent that was only ever stated in prose nothing shares
with dependents.

**Resolved (`D34`): the "is `Purpose` clean enough to extract
mechanically" question.** `component.md`'s anatomy now has a dedicated
`Rationale` section (`SPEC_GUIDELINES.md` §3.4) — `Purpose` MUST be
dependent-safe (no decision citations, no historical justification),
enforced by a real lint rule (`R-LINT-024`), not left as an unchecked
convention. All 13 components whose `Purpose` mixed "what" with "why
this design was chosen" have been retrofitted. This means the context
view, when built, can take the *entire* `Purpose` section verbatim —
no fragile "first paragraph" extraction needed, since `Purpose` is now
guaranteed clean by construction.

**Still open, now that `Purpose` is ready to be extracted:**
- Is the view itself a *new* one (`component_context`, extending
  `graph-query-engine.md`'s `component_docs` pattern — join
  frontmatter + `Purpose`-section text, same regex-extraction technique
  `rule_ratified_closure` already uses for `Open questions`), or does
  `spec-bundle-assembler` just query `component_docs` directly and pull
  `Purpose` out itself?
- `R-ASSEMBLE-002` currently excludes `component.md` from
  `dependency_interfaces` *entirely* ("never its `component.md`") — this
  idea requires carving a narrow, explicit exception for just `Purpose`
  into that rule, not reopening it wholesale. `requirements/` and
  `constraints.md` should stay excluded; if something in a dependency's
  constraints is genuinely dependent-relevant, the existing mechanism
  for that is a proper `interface/guarantees/G-id.md` entry, not a
  second channel for the same fact.
- Does "concise" need a hard length cap on `Purpose` (another D2-style
  size discipline), or is "one paragraph" (already the rule) enough on
  its own now that it can't carry rationale padding anymore?

---

## Four gaps found during the `D31`/`D32` corpus-wide audit, not yet acted on

**`GoldenScenarioReport` has no `rationale` field.** Golden scenarios can
be `llm-judge`-kind (`R-GOLDEN-001`), but unlike `VerificationReport`'s
`criteria` entries (which carry `rationale` for exactly this case),
`GoldenScenarioReport` has nowhere to put a judge's reasoning when one
fires. A failing or skipped judgment-based golden scenario's *why* is
structurally unrecorded. High confidence this is a real gap, not a
deliberate minimization (nothing argues for omitting it the way `D17`
argued for `retry_feedback`'s own content limits).

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
