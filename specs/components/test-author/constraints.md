# Test Author — Non-Functional Constraints

- **Not deterministic, and that's expected — but bounded**, same posture as
  `generator`'s own constraints.md: a cache hit MUST be byte-identical for
  the same key; the recorded `seed`/model MUST match what was actually
  requested.
- **One model is enough.** Selection MUST NOT fail or block when only
  one model is available (R-AUTHOR-003).
- **No silent partial output.** A model-call error MUST leave
  `verification/<component>/generated-test/` untouched for that criterion.
- **Credential handling.** Mirrors `generator`'s constraint exactly, for
  both credentials this component may use.
