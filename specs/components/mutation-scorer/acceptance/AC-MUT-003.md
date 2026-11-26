# AC-MUT-003

Covers: R-MUT-003
Kind: generated-test

```gherkin
Given JS = "function f(a, b) { return a === b; }" + " " * 200, qux.py
  exactly f'"""Doc."""\n\nSCRIPT = {JS!r}\n\n\ndef qux():\n    return 4\n',
  and one test asserting qux.qux() == 4
When score is called
Then mutation_score is None and mutation_error is exactly
  "javascript in a string at qux.py:3; declare it as an asset (specs/architecture/asset-kinds.md)"

Given qux.py is instead f'{JS!r}\n\n\ndef qux():\n    return 4\n'
When score is called
Then mutation_error is None and mutation_score is 1.0

Given qux.py defining qux() whose loop "while i < x: i = i + 1" has a
  mutant that never terminates, and one test covering it
When score is called
Then it returns within ten seconds and killed equals mutants
```
