# Library

```
lint(paths: list[Path] | None, repo_root: Path, strict: bool = False, judge=None) -> LintReport
load_corpus(repo_root: Path) -> Corpus
```

A pure function over the filesystem state at `repo_root` — no network
access, no model calls, no side effects. `paths=None` lints the whole
corpus. `judge` is optional, for `R-LINT-015`'s model-backed check;
omitted, it reports `skipped` rather than running or crashing. It is
called as `judge(term, local_text, glossary_text)` and returns
`(conflicts, rationale)`, a conflict when `conflicts` is true, or `None`
when it could not judge, also reported `skipped`.

`load_corpus` is `corpus-loader`'s, re-exported unchanged; `lint` and both
checkers load their corpus through it. `corpus-loader`, `citation-checker`
and `size-checker` load from `<repo_root>/gen/<slug>/`, or the same path
under the tool root (`D199`).

Implements: `SPEC_GUIDELINES.md`, `specs/architecture/graph-query-engine.md`, `specs/architecture/cli-conventions.md`, `specs/architecture/asset-kinds.md`
