# Library

```
verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport
```

`judge` is the same injectable-callable pattern as `spec-linter`'s
R-LINT-015 — omit it to run with every `llm-judge` criterion reporting
`skipped`. `test_author` is the equivalent for `generated-test` criteria
lacking a cached test (R-VERIFY-009) — **but omitting it degrades
differently**: a `generated-test` criterion with nothing cached and no
`test_author` configured reports `fail`, not `skipped` (R-VERIFY-010).
