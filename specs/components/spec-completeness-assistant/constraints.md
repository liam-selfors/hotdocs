# Spec Completeness Assistant — Non-Functional Constraints

- **Never a gate.** This is a structural property, not a convention to be
  followed: no code path in this component, and no entry in any other
  component's `depends_on` or `provenance-tracker`'s own checks, gives
  it any way to block a merge. If a future change ever needs this
  component's judgment to be load-bearing, that is a different, new
  capability — not a tightening of this one.
- **Fast enough for iteration.** This runs repeatedly during feature-branch
  development, not once at commit time — it SHOULD be noticeably cheaper
  and faster than running `hotdocs generate` against every impacted
  component: it never generates code, and makes at most two model calls
  of its own (R-ASSIST-010).
- **Graceful degradation, not a hard model requirement.** Per R-ASSIST-007,
  this component keeps producing useful output (lint + blast radius + criterion
  reviews) even with no model configured at all — unlike most gates in this
  corpus, whose primary model is effectively required (`VAR-ANTHROPIC-API-
  KEY` is `required: yes`), this component's *judgment* half is allowed to
  be fully absent without the tool becoming useless.
