# `decision_lineage` (view)

```
id                     TEXT  -- "D<N>"
last_ratified_commit   TEXT  -- NULL until ratified; retained after deprecation
```

One row per `specs/decisions/*.md` file (`R-GQE-008`). Everything
else about a decision (`status`, `supersedes`, `builds_on`) is a
`nodes`/`edges` fact instead (`kind = 'decision'`, `edge_type IN
('supersedes', 'builds_on')`) (`D74`).
