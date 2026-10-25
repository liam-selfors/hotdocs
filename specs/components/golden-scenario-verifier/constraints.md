# Golden Scenario Verifier — Non-Functional Constraints

- **Determinism of dispatch, not of everything dispatched to.** This
  component's own capability-intersection lookup and aggregation MUST be
  deterministic given the same blast radius and corpus state; an injected
  `llm-judge` or `test_author` callable's actual output is explicitly not
  covered by that guarantee — the same caveat `verifier-orchestrator`'s
  own constraints already state, for the same reason.
- **`kind:` is read-only input, never written.** Same invariant
  `verifier-orchestrator` honors: a golden scenario's declared `kind` is
  fixed at spec-authoring time and never reinterpreted here.
- **Never conflated with a single component's own verification result.**
  `GoldenScenarioReport` is a distinct namespace (`P-id`-keyed) from any
  component's `VerificationReport` — a cross-component finding and a
  single-component finding point a developer to different places to fix
  the problem.
