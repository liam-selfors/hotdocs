# Library

```
run_capability_scenarios(blast_radius: list[str], repo_root: Path, judge=None, test_author=None) -> CapabilityScenarioReport
```

`judge`/`test_author` are the same injectable-callable pattern
`verifier-orchestrator`'s `verify()` already uses — `merge-orchestrator`
wires the real implementations into this call too (`R-MERGE-014`), the
same way `R-MERGE-004` wires them into `verifier-orchestrator`'s call;
two separate wiring sites, same real callables. Omitting either degrades
the same way it does for `verifier-orchestrator`: an `llm-judge` scenario
reports `skipped`; a `generated-test` scenario with nothing cached and no
`test_author` configured reports `fail`.
