# Library

```
compile(component_id: str, repo_root: Path, target: str = "pytest") -> CompileReport
```

A pure function over corpus state at `repo_root` — no network access, no
model calls, no side effects beyond writing the files it's asked to write.
(Previously `compile(acceptance_md: Path, interface_md: Path, target: str =
"pytest")`, taking two explicit file paths; updated for D15's
one-file-per-unit layout, where a component's `acceptance/` and
`interface/` are directories at known paths given its id, not individual
files to pass in by hand.)
