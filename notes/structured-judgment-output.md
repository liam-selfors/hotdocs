# Structured Judgment Output Pattern

_Working notes. Non-normative. `SPEC_GUIDELINES.md` §5 already states
the underlying rule ("an `llm-judge` criterion MUST emit structured
rationale alongside its verdict") — this file is the pattern that rule
compresses, derived independently four separate times before it became
explicit. Started: 2026-10-26._

Any time a field in this corpus reports a verdict that *could* have
come from judgment rather than a mechanical check, ask whether it has
a place to record **why** — not as a nice-to-have, but because this
corpus has now hit the same gap four times: `Finding` (`spec-linter`),
`VerificationReport.criteria[]`, `CapabilityScenarioReport.scenarios[]`
(`D23`), and `redundancy_flags` (`D28`, `spec-completeness-assistant`).
Every one of them needed a `rationale`-shaped field once a judgment
case actually exercised them.

## The shape

`{result, rationale}` (or the kind-appropriate equivalent — `failure_detail`
for a `compiled`/`generated-test` failure, `D27`, is the same pattern
applied to a different question: not "why did a judge decide this" but
"what exactly failed"). The pairing is the reusable part, not the exact
field names.

## The one subtlety that's easy to get backwards

Whether `rationale` is **optional** or **mandatory** depends on what
the *container* holds, not on the field in isolation:

- **Optional**, when the container mixes entries that fired with
  entries that didn't. `VerificationReport.criteria[]` holds every
  criterion regardless of `kind` or outcome — a `compiled` `pass` sits
  next to a `skipped` `llm-judge` entry in the same array, so
  `rationale` can only be populated for the subset that's actually
  judgment-based and actually ran.
- **Mandatory**, when the container *only ever* holds entries that
  already fired. `redundancy_flags` has no "flagged but uninteresting"
  state — an entry exists in that array only because a real judgment
  call actually found something, so there is no "fired but
  unexplained" case to accommodate, and `rationale` is required on
  every entry rather than nullable.

Get this backwards (mandatory where it should be optional, or vice
versa) and either you've made a legitimate "not yet evaluated" case
impossible to represent, or you've left a judgment call with nowhere
to record why it fired.

## Checklist for a new field

1. Does this field's value ever come from an `llm-judge`-kind call, or
   anything else non-deterministic?
2. If yes: does its container also hold non-judgment or never-fired
   entries in the same array/shape? → `rationale` optional, null-able.
3. If the container only ever holds entries that already fired
   (filtered, not a full enumeration)? → `rationale` mandatory.
4. Don't invent a new container shape to unify this with an unrelated
   field just because both have a `{result, rationale}` core — `D23`'s
   analysis explicitly rejected forcing
   `Finding`, `VerificationReport.criteria[]`, `CompletenessReport`, and
   `CapabilityScenarioReport.scenarios[]` into one universal type. Share
   the micro-shape; keep each container's own shape driven by its own
   consumers.
