# Library

```
verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport
GATE_VERSION: str  # "verifier-orchestrator@4.0.0" (R-VERIFY-015)
DEFAULT_TEST_TIMEOUT: float  # 300.0, read at each run (R-VERIFY-014)
```

`verify` returns a **dataclass** whose fields are attributes
(`report.overall`, `report.criteria`), with `to_dict()` giving the JSON
form. Each `criteria` entry is a plain **dict** (`c["id"]`,
`c["result"]`), as is `requirement_results` (`D190`).

`judge`/`test_author` are the glossary's "Injected `judge`/`test_author`
callable shape" (`D65`): one `bundle` argument.

It loads `spec-bundle-assembler`, `run-environment`, `test-supply` and
`mutation-scorer` from `<repo_root>/gen/<slug>/` and the sealed
`criterion-compiler` from `<repo_root>/pipeline/criterion-compiler/`, each
else from the tool root (`D199`).

Implements: `specs/architecture/step-phrase-grammar.md`, `specs/architecture/acceptance-criteria.md`, `specs/architecture/verifier-fixtures.md`, `specs/architecture/cli-conventions.md`, `specs/architecture/run-environment.md`
