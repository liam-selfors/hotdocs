# Generation Loop — Non-Functional Constraints

- **Only requirement ids reach the generator.** The feedback is built
  from criteria's `covers` values alone, never their text, rationale or
  failure detail (`R-GEN-012`).
- **Bounded.** At most `max_attempts` generations per call, and no
  attempt after an error that a new attempt cannot fix.
- **No hidden attempts.** Every attempt is passed to `on_attempt` and
  listed in the result.
