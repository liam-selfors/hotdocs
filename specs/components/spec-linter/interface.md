---
id: comp-spec-linter-interface
title: Spec Linter — Interface
status: draft
owners: [pipeline-team]
---

# Spec Linter — Interface

## CLI

```
hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]
```

- `<path>...` — one or more files or directories under `specs/` to lint.
  Defaults to the whole `specs/` tree.
- `--format` — `text` (human-readable, default) or `json` (the `LintReport`
  schema below).
- `--strict` — treat `warn`-severity findings as failures too.
- `--repo-root` — repository root, for resolving the corpus and
  `specs/glossary.md`. Defaults to the current git repository root.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | No `fail`-severity findings (warnings and `skipped` findings may be present, even under `--strict` — `skipped` is never promoted to a failure; it means "not evaluated," not "passed" or "violated"). |
| `1` | ≥1 `fail`-severity finding. |
| `2` | Usage error (bad arguments, unreadable path). |

## Library

```
lint(paths: list[Path], repo_root: Path, strict: bool = False) -> LintReport
```

A pure function over the filesystem state at `repo_root` — no network
access, no model calls, no side effects.

## Data: `LintReport`

```json
{
  "findings": [
    {
      "rule_id": "R-LINT-003",
      "severity": "fail",
      "file": "specs/components/foo/spec.md",
      "line": 12,
      "message": "depends_on references 'comp-bar', which does not exist"
    },
    {
      "rule_id": "R-LINT-015",
      "severity": "skipped",
      "file": "specs/components/foo/spec.md",
      "line": 8,
      "message": "no model configured — R-LINT-015 not evaluated",
      "rationale": null
    }
  ],
  "summary": {
    "hard_failures": 1,
    "warnings": 0,
    "skipped": 1
  }
}
```

`rule_id` always corresponds to an `R-LINT-NNN` id in `spec.md`'s Behavior
section — this is how a reviewer traces a reported finding back to the
requirement that produced it.

- `severity` is one of `fail` / `warn` / `skipped`. `skipped` exists only for
  `kind: llm-judge` rules when no model is configured (R-LINT-015 currently)
  — the D10-pattern graceful degradation, visible rather than silent, never
  conflated with a pass.
- `rationale` (optional, string) is present when the finding came from an
  `llm-judge` evaluation that actually ran, per `SPEC_GUIDELINES.md` §5's
  requirement that `llm-judge` criteria emit structured rationale. Absent or
  `null` for every other `severity`/`rule_id` combination.
