# Library

```
lint(paths: list[Path], repo_root: Path, strict: bool = False) -> LintReport
```

A pure function over the filesystem state at `repo_root` — no network
access, no model calls, no side effects.
