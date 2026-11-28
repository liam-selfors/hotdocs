# Spec Completeness Assistant — Non-Functional Constraints

- **Fast enough for iteration.** This runs repeatedly during feature-branch
  development, not once at commit time — it SHOULD be noticeably cheaper
  and faster than running `hotdocs generate` against every impacted
  component: it never generates code, and makes at most two model calls
  of its own (R-ASSIST-010).
