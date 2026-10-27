# Library

```
run_capability_scenarios(blast_radius: list[str], repo_root: Path, judge=None, test_author=None) -> CapabilityScenarioReport
```

`judge`/`test_author` are the glossary's "Injected `judge`/`test_author`
callable shape" (`D65`) — the same single-`bundle`-argument convention
`verifier-orchestrator`'s `verify()` uses, read duck-typed on the way
out (a dict with `result`/`verdict`/`model_call_error`/`file` keys, or
an object with the same attributes). `merge-orchestrator` wires the
real implementations into this call too (`R-MERGE-014`) — the same
closures it passes into every `component-gate-runner` call for
`verifier-orchestrator`'s own use (`D76`); one wiring site, not two.
Omitting either degrades
the same way it does for `verifier-orchestrator`: an `llm-judge` scenario
reports `skipped`; a `generated-test` scenario with nothing cached and no
`test_author` configured reports `fail`.
