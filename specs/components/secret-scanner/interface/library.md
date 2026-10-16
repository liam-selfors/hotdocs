# Library

```
scan(repo_root: Path) -> SecretScanResult
scan_files(paths: list[Path]) -> SecretScanResult
```

`scan` is the full, cache-aware form. `scan_files` is the precommit form —
no cache lookup, no `gate_version` dependency, since it's meant to run
before a commit exists to key anything on.
