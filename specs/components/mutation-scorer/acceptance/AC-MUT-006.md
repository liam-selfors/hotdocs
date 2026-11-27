# AC-MUT-006

Covers: R-MUT-003
Kind: generated-test

```gherkin
Given qux.py exactly f'SCRIPT = {S!r}\n\n\ndef qux():\n    return 4\n'
  and one test asserting qux.qux() == 4, for each S below
When score is called
Then mutation_error is as listed, None meaning a score was computed:
  | S                                                   | mutation_error |
  | "function f(a) { return a; }" + " " * 200           | the line-1 message |
  | "function f(a) ; return a" + " " * 200              | the line-1 message |
  | "function f(a) { return a; }" + " " * 100           | None           |
  | "plain words, no code here; {x}" + " " * 200        | None           |
  | "function f(a) return a" + " " * 200                | None           |
  where the line-1 message is exactly "javascript in a string at
  qux.py:1; declare it as an asset (specs/architecture/asset-kinds.md)"
```
