---
id: comp-spec-completeness-assistant
title: Spec Completeness Assistant
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-impact-analyzer, comp-spec-bundle-assembler, comp-generator]
realizes: [P-AMBIGUITY-GATE]
uses_var: [VAR-ANTHROPIC-API-KEY]
model_pin: claude-sonnet-5
sealed: false
---

# Spec Completeness Assistant

## Purpose

The assist agent D1 describes but never names: helps a developer land a
*complete* spec change on a feature branch — dependencies updated, no
logical discrepancies, no redundancies — using hint-mode previews to
evaluate completeness **before** a change is even submitted to the real
merge pipeline. This is the component `notes/metrics.md` already assumes
exists (its "Completeness-agent confidence" and "Assist-agent acceptance
rate" metrics predate this spec) but that, until now, had never actually
been specced.

## Scope

**In scope:** running the cheap, deterministic checks first (lint, blast
radius); producing a hint-mode preview; producing a judgment-based
completeness assessment and a redundancy/overlap check.

**Out of scope, and load-bearing, not incidental:** gating anything. This
component's output is advisory only — it is never in `merge-orchestrator`'s
dependency list, and it has no mechanism to block a merge. The actual gates
(`spec-linter` at hard-fail severity, `verifier-orchestrator`, the
compliance scans) are the only things that can do that; this component
exists entirely on the feature-branch side of D1's cold-vs-hint split,
never the merge side. Also out of scope: **re-deciding anything a ratified
spec already declares** — same boundary `verifier-orchestrator`/
`test-author` observe for a criterion's `kind:`. This component may
*suggest* a spec change before ratification; it has no standing to override
one after.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

- **R-ASSIST-001** — MUST run `spec-linter` against the draft spec change
  first, and surface any hard-fail finding to the developer immediately —
  before any judgment-based analysis runs. Same "cheap, deterministic gate
  first" ordering `merge-orchestrator` already uses (R-MERGE-001), applied
  here on the feature-branch side.
- **R-ASSIST-002** — MUST compute the predicted blast radius via
  `impact-analyzer` for the draft change and surface it — this is the
  "Predicted blast radius" metric (`notes/metrics.md`, Ideation phase),
  which had no component computing it until now.
- **R-ASSIST-003** — MUST produce a hint-mode preview (via
  `spec-bundle-assembler` in `hint` mode, then `generator`) for each
  component in the predicted blast radius — D1's exact described use of
  hint mode, concretely implemented here for the first time.
- **R-ASSIST-004** — MUST produce a completeness confidence score (0.0–1.0)
  with structured rationale: whether touched requirements have present,
  non-trivial acceptance criteria; whether a dependent's `interface.md`
  looks like it needs a matching update that wasn't made; whether the
  change's `Definitions` entries conflict with the glossary (reusing
  `spec-linter`'s R-LINT-011/015 distinction — this component does not
  reimplement that detection, it surfaces `spec-linter`'s own findings
  plus whatever this component's own broader judgment adds on top).
- **R-ASSIST-005** — MUST run a redundancy/overlap check — does this change
  restate behavior already specified elsewhere in the corpus — matching the
  "Overlap / duplication score" metric (`notes/metrics.md`, Ideation
  phase). Judgment-based: detecting that two differently-worded passages
  describe the same behavior is semantic, not structural, the same category
  of problem `spec-linter`'s R-LINT-015 was split out for.
- **R-ASSIST-006** — This component's output MUST NOT gate anything. It
  MUST NOT appear in `merge-orchestrator`'s `depends_on`, and its result
  MUST have no mechanism by which it can block a merge — advisory only, by
  construction, not by developer discipline.
- **R-ASSIST-007** — When no model is configured, MUST degrade to only
  R-ASSIST-001–003 (the compiled/hint-mode-preview checks, which need no
  model beyond what `generator` itself already requires) and MUST report
  R-ASSIST-004/005 as `skipped` — the same graceful-degradation posture
  `spec-linter`'s R-LINT-015 established, now a further instance.
- **R-ASSIST-008** — A developer's response to this component's suggestions
  (accepted / overridden) SHOULD be recorded to feed the "Assist-agent
  acceptance rate" metric (`notes/metrics.md`) — but *capturing and storing*
  that response is explicitly out of scope for this component's own
  behavior (a UI/tooling-layer concern, not specced here); this requirement
  only establishes that the hook for doing so exists.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`CompletenessReport` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Whether this component should itself get a second-model cross-check for
  R-ASSIST-004/005 (two independent completeness judgments, compared) — the
  same question left open for `test-author`. Not addressed here; a
  plausible future refinement, not assumed.

## Change log

- Initial draft.
