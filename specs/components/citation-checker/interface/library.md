# Library

```
check(repo_root: Path) -> list[dict]
```

Loads the corpus with `corpus-loader`'s `load_corpus(repo_root)`, from
`<repo_root>/gen/corpus-loader/` or the same path under the tool root,
the parent of the nearest `gen` directory above this module's own file
(`D199`), and returns this component's findings. Each is a dict with
exactly `rule_id` (the requirement that produced it), `severity`
(`fail` or `warn`), `file` (relative to `repo_root`), `line` (an `int`,
`1` when no better line applies) and `message`, in the order of the
corpus's sorted file paths.

Implements: `specs/architecture/glossary-and-citations.md`
