# Library

```
assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle
assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle
```

Both are pure functions over the filesystem state at `repo_root` — no
network access, no model calls, no side effects.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/test-reuse.md`, `specs/architecture/asset-kinds.md`
