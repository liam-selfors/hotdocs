# Library

```
verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport
GATE_VERSION: str  # "verifier-orchestrator@2.0.0" (R-VERIFY-015)
```

`verify` returns an **object** whose fields are attributes
(`report.overall`, `report.criteria`), with a `to_dict()` giving the
JSON form. Each `criteria` entry is a plain **dict** (`c["id"]`,
`c["result"]`), as is `requirement_results`: never a bare-dict report,
never criterion objects (`D190`).

`judge`/`test_author` are the glossary's "Injected `judge`/`test_author`
callable shape" (`D65`) — a single-`bundle`-argument convention,
**not** the same shape as `spec-linter`'s own `judge` parameter
(`R-LINT-015`), which takes three positional arguments for a narrower
task. Omit `judge` to run with every `llm-judge` criterion reporting
`skipped`. `test_author` is the equivalent for `generated-test` criteria
lacking a cached test (R-VERIFY-009) — **but omitting it degrades
differently**: a `generated-test` criterion with nothing cached and no
`test_author` configured reports `fail`, not `skipped` (R-VERIFY-010).
