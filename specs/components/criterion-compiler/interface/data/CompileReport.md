# `CompileReport`

```json
{
  "outputs": [
    {
      "criterion_id": "AC-LINT-003",
      "covers": "R-LINT-003",
      "status": "compiled",
      "file": "verification/spec-linter/compiled/test_ac_lint_003.py"
    },
    {
      "criterion_id": "AC-LINT-999",
      "covers": "R-LINT-999",
      "status": "error",
      "file": "specs/components/spec-linter/acceptance/AC-LINT-999.md",
      "message": "line 7: step 'When a wizard appears' does not match any recognized template"
    }
  ],
  "gate_version": "criterion-compiler@1.0.0",
  "summary": {
    "compiled": 14,
    "errors": 0,
    "skipped_non_compiled_kind": 0
  }
}
```

`compile` returns a `CompileReport` dataclass with attributes `outputs`
(dicts as above), `gate_version` and `summary` (a dict). An entry's `file` is the emitted test for `compiled`, the acceptance
file for `error`, both repo-relative. An error's
`message` begins `line <n>: `, `<n>` the offending step's 1-based line
in its acceptance file (for `compile_criterion`, in its `gherkin`), then
quotes the offending name, or the step as written with its
keyword (`step 'When a wizard appears' does not match any recognized
template`) for an unmatched step, `unresolved
reference '<name>'` for an identifier no earlier `Given` binds, `does not
resolve` for a name the interface lacks, and `is not a literal`
for an expression, plus `field/index access` when it is one.

`gate_version` corresponds to the `gate_versions.compiler` entry in the
provenance manifest described in `notes/initial-ideas.md`'s own D7
(R-COMPILE-010).
