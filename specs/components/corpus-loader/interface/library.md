# Library

```
load_corpus(repo_root: Path) -> Corpus
```

Returns the `Corpus` its data document defines, for the corpus under
`repo_root/specs/`. `graph-query-engine` is loaded from
`<repo_root>/gen/graph-query-engine/`, or the same path under the tool
root, the parent of the nearest `gen` directory above this module's own
file (`D199`).
