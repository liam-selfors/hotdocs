# AC-VERIFY-032

Covers: R-VERIFY-006
Kind: generated-test

```gherkin
Given JS = "function f(a, b) { return a === b; }" + " " * 200 and
  comp-qux whose gen/qux/qux.py is exactly
  f'"""Doc."""\n\nSCRIPT = {JS!r}\n\n\ndef qux():\n    return 4\n',
  and one cached generated test asserting qux.qux() == 4
When verify runs
Then that criterion is pass, mutation_score is None, overall is "fail"
  and mutation_error is exactly
  "javascript in a string at qux.py:3; declare it as an asset (specs/architecture/asset-kinds.md)"

Given qux.py is instead f'{JS!r}\n\n\ndef qux():\n    return 4\n', JS
  being its docstring
When verify runs
Then mutation_error is None and mutation_score is 1.0
```
