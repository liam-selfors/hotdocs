# AC-KJS-013

Covers: R-KJS-005
Kind: generated-test

```gherkin
Given the source of the module under test, read from
  Path(kind_javascript.__file__) and parsed with ast.parse
When every ast.Constant whose value is a str is examined
Then no such str both matches the regular expression
  r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s" and contains ";" or "{"
  while being 200 characters or longer
```
