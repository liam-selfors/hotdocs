# Library

```
verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport
GATE_VERSION: str  # "verifier-orchestrator@2.2.0" (R-VERIFY-015)
```

`verify` returns a **dataclass** instance whose fields are attributes
(`report.overall`, `report.criteria`), with a `to_dict()` giving the
JSON form. Each `criteria` entry is a plain **dict** (`c["id"]`,
`c["result"]`), as is `requirement_results`: never a bare-dict report,
never criterion objects (`D190`).

`judge`/`test_author` are the glossary's "Injected `judge`/`test_author`
callable shape" (`D65`): one `bundle` argument, unlike `spec-linter`'s
three-argument `judge` (`R-LINT-015`). Omit `judge` to run with every `llm-judge` criterion reporting
`skipped`. `test_author` is the equivalent for `generated-test` criteria
lacking a cached test (R-VERIFY-009) — **but omitting it degrades
differently**: a `generated-test` criterion with nothing cached and no
`test_author` configured reports `fail`, not `skipped` (R-VERIFY-010).

It loads `spec-bundle-assembler` from `<repo_root>/gen/spec-bundle-assembler/`
and the sealed `criterion-compiler` from
`<repo_root>/pipeline/criterion-compiler/`, either else from the tool
root (`D199`). How a test builds its fixture is in
`specs/architecture/verifier-fixtures.md`.

Implements: `specs/architecture/step-phrase-grammar.md`, `SPEC_GUIDELINES.md`, `specs/architecture/verifier-fixtures.md`, `specs/architecture/mutation-runs.md`
