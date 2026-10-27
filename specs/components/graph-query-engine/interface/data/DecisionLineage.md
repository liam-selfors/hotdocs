# `decision_lineage` (view)

```
id                     TEXT  -- "D<N>"
title                  TEXT
status                 TEXT  -- draft | ratified | deprecated
last_ratified_commit   TEXT  -- NULL until ratified; retained after deprecation
supersedes             TEXT  -- "D<N>" of the prior record this one replaces, or NULL
```

One row per `specs/decisions/*.md` file (`R-GQE-008`). `supersedes`
is `NULL` for the overwhelming majority of rows today — only `D31`
sets it (`D88`). A row whose `supersedes` is non-`NULL` names a
decision that MUST itself have `status: deprecated` (`R-LINT-029`).
