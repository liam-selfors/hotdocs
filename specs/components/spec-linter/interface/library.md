# Library

```
lint(paths: list[Path] | None, repo_root: Path, strict: bool = False, judge=None) -> LintReport
load_corpus(repo_root: Path) -> Corpus
```

A pure function over the filesystem state at `repo_root` — no network
access, no model calls, no side effects. `paths=None` lints the whole
corpus. `judge` is optional, for `R-LINT-015`'s model-backed check;
omitted, it reports `skipped` rather than running or crashing.

Implements: `SPEC_GUIDELINES.md`, `specs/architecture/graph-query-engine.md`
