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
    }
  ],
  "summary": { "hard_failures": 1, "warnings": 0, "skipped": 0 }
}
```

`lint` returns a `LintReport` dataclass: `findings`, a list of
`Finding(rule_id, severity, file, line, message, rationale=None)`
dataclasses, and read-only `hard_failures`, `warnings` and `skipped`
counts. Their `to_json()` gives the JSON above, with `rationale` only
when set. `severity` is `fail`, `warn` or `skipped` (R-LINT-015 with no
model). `rationale` is set only when an `llm-judge` evaluation ran
(`SPEC_GUIDELINES.md` §5).
