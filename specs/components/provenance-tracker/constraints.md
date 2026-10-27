# Provenance Tracker — Non-Functional Constraints

- **This component itself makes no model calls — the components it
  calls might.** `check_readiness` is pure sequencing and aggregation;
  any model call that actually happens (a cache-miss `hotdocs build` on
  a component, a stale capability's scenarios re-running) is
  `component-gate-runner`'s or `capability-scenario-verifier`'s own
  cost, incurred inside their own real function calls, not this
  component's. Unlike the read-only `hotdocs verify` this replaced
  (`D88`), `hotdocs build` can genuinely be slow and cost real money —
  that is expected, not a regression.
- **Never a gate input.** `hotdocs build` answers a question and acts
  on it; nothing requires it to be run before a commit, and no
  component's own pass/fail decision reads this component's output
  (`D87`).
- **`AttemptRecord` is append-only, never mutated** — written by
  `component-gate-runner` (`R-GATE-008`), read-only from this
  component's own side. This component MUST NOT write, edit, or delete
  anything under `.hotdocs/attempts/` itself.
- **Determinism of sequencing, not of everything sequenced.** Given the
  same mocked `run_component_gates`/`run_capability_gates` outputs,
  `check_readiness`'s own call order and `VerifyReport` assembly MUST
  be reproducible — a claim about this component's own logic, not a
  claim that two real `hotdocs build` runs against a changing corpus
  produce identical reports.
- **No retention/eviction policy specified here.** `.hotdocs/attempts/`
  growing without bound over a long-lived local checkout is a real,
  known cost — deliberately left unaddressed in this version, the same
  posture `cache-manager`'s own eviction-policy open question already
  has. Local, gitignored, disposable data a developer can delete at any
  time with no correctness consequence.
