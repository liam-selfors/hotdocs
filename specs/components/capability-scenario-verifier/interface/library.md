# Library

```
run_capability_scenarios(blast_radius: list[str], repo_root: Path, judge=None, test_author=None) -> CapabilityScenarioReport
```

`judge`/`test_author` are the glossary's "Injected `judge`/`test_author`
callable shape" (`D65`) — the same single-`bundle`-argument convention
`verifier-orchestrator`'s `verify()` uses, read duck-typed on the way
out (a dict with `result`/`verdict`/`model_call_error`/`file` keys, or
an object with the same attributes). A developer running
`hotdocs check-capability` (`D89`) supplies these the same way
`hotdocs generate` does for `component-gate-runner` — this component
wires its own, no caller does it on its behalf. Omitting either
degrades the same way it does for `verifier-orchestrator`: an
`llm-judge` scenario reports `skipped`; a `generated-test` scenario
with nothing cached and no `test_author` configured reports `fail`.

```
check_capability_provenance(capability_id: str, repo_root: Path) -> CapabilityProvenanceCheckResult
run_capability_gates(capability_id: str, repo_root: Path, judge=None, test_author=None) -> CapabilityProvenanceCheckResult
```

`R-SCENARIO-004`, `D89` — see that requirement for the provenance key
and check-then-run behavior.
