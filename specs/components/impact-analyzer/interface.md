---
id: comp-impact-analyzer-interface
title: Impact Analyzer — Interface
status: draft
owners: [pipeline-team]
---

# Impact Analyzer — Interface

## CLI

```
hotdocs impact --changed <spec-id>... [--repo-root=<dir>] [--format=json|text]
```

- `--changed <spec-id>...` — one or more spec ids known to have changed in
  this diff (as determined by the caller, e.g. from `git diff`'s changed
  paths resolved to spec ids). Required, ≥1.
- `--repo-root` — defaults to the current git repository root.
- `--format` — `text` (human-readable, default) or `json` (the
  `BlastRadiusReport` schema below).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Blast radius computed successfully (may be empty if nothing depends on the changed ids and none are themselves components). |
| `1` | Precondition failure — the corpus did not pass `spec-linter` cleanly (R-IMPACT-007). |
| `2` | Usage error (no `--changed` ids given, an id that doesn't exist in the corpus at all). |

## Library

```
compute_blast_radius(changed_ids: list[str], repo_root: Path) -> BlastRadiusReport
```

A pure function over the filesystem state at `repo_root` — no network
access, no model calls, no side effects. Raises/returns an explicit
precondition-failure result (not a best-effort partial one) if the corpus
graph isn't lint-clean.

## Data: `BlastRadiusReport`

```json
{
  "impacted": [
    {
      "component_id": "comp-foo",
      "reason": "direct",
      "via": null
    },
    {
      "component_id": "comp-bar",
      "reason": "transitive-interface",
      "via": "comp-foo"
    },
    {
      "component_id": "comp-baz",
      "reason": "transitive-var",
      "via": "VAR-CACHE-STORE-URL"
    },
    {
      "component_id": "comp-qux",
      "reason": "transitive-capability",
      "via": "P-ZERO-EDIT"
    }
  ],
  "precondition_error": null
}
```

`reason` is always one of `direct` | `transitive-interface` |
`transitive-var` | `transitive-capability` (R-IMPACT-001/003/004/005). `via`
names the specific upstream id that triggered inclusion, `null` only for
`direct`. A non-null `precondition_error` means `impacted` is empty and MUST
be ignored by callers (R-IMPACT-007) — it is not "nothing was impacted," it
is "the question could not be answered."
