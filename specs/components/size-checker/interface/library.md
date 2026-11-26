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

Each finding's `message` is exactly, `<name>` the bare component name
(`foo` for `comp-foo`), `<severity>` `warn` or `fail`, `<limit>` the
threshold exceeded:

- `R-SIZE-001`: `<name>: <dimension> is <value>, above the <severity> threshold of <limit> (specs/architecture/size-caps.md)`
- `R-SIZE-002`: `<name>: <n> size-cap dimensions over their warn thresholds at once (<dimension>=<value>, ...); see specs/architecture/size-caps.md's decomposition-signal rule`,
  the dimensions in `R-SIZE-001`'s order, joined by `, `
- `R-SIZE-003`: `<file> has <words> words, above the per-file <severity> threshold of <limit>`, `<file>` relative to `repo_root`
- `R-SIZE-004`: `<name>: Purpose section has <words> words, above the <severity> threshold of <limit> (specs/architecture/size-caps.md)`

Implements: `specs/architecture/size-caps.md`
