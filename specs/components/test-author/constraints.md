# Test Author — Non-Functional Constraints

- **Not deterministic, and that's expected — but bounded**, same posture as
  `generator`'s own constraints.md: a cache hit MUST be byte-identical for
  the same key; the recorded `seed`/model MUST match what was actually
  requested.
- **Independence is a preference, not a hard requirement.** Model selection
  prefers a different model than `generator` used (R-AUTHOR-003), but MUST
  NOT fail or block when only one model is available — consistent with D10
  and every other instance of this posture in the corpus.
- **No silent partial output.** A model-call error MUST leave
  `verification/<component>/generated-test/` untouched for that criterion.
- **Credential handling.** Mirrors `generator`'s constraint exactly, for
  both credentials this component may use.
