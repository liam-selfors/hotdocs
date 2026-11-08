# `LintReport`

```json
{
  "findings": [
    {
      "rule_id": "R-LINT-003",
      "severity": "fail",
      "file": "specs/components/foo/component.md",
      "line": 12,
      "message": "depends_on references 'comp-bar', which does not exist"
    },
    {
      "rule_id": "R-LINT-015",
      "severity": "skipped",
      "file": "specs/components/foo/component.md",
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

`rule_id` is the `R-LINT-NNN` requirement that produced the finding.

- `severity` is `fail`, `warn` or `skipped`; `skipped` only for an
  `llm-judge` rule with no model configured (R-LINT-015), never a pass.
- `rationale` (optional) is present only when an `llm-judge` evaluation
  ran (`SPEC_GUIDELINES.md` §5).
