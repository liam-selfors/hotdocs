# `DriftReport`

```json
{
  "entries": [
    {
      "file": "specs/components/foo/requirements/R-FOO-001.md",
      "cited_decision": "D17",
      "superseded_by": "D31",
      "file_commit": "2a68165",
      "superseder_ratified_commit": "86ab93f"
    }
  ]
}
```

One entry per `(file, cited_decision)` pair where `R-DRIFT-002`'s
ancestry check found the file's own last-touching commit predates the
superseding decision's ratification. An empty `entries` list is a
clean result — every live citation is either unsuperseded or already
reflects whatever superseded it.
