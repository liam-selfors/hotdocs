# Product Capabilities

Capabilities, each with a stable `P-<id>`, and their own Given/When/Then
capability scenarios exercised **black-box against the whole assembled system** —
never against one component in isolation.

See `SPEC_GUIDELINES.md` §3.1.

- **`P-ZERO-EDIT`** — zero-human-edit merge (the methodology's headline claim).
- **`P-AMBIGUITY-GATE`** — ambiguity caught before merge, not after.
- **`P-COMPLIANCE-GATE`** — secrets/license risk never reaches `main` silently.
- **`P-MERGE-VISIBILITY`** — a partially-failed merge's status is durable
  and queryable per component, and correcting the failure recovers the
  rest for free.
