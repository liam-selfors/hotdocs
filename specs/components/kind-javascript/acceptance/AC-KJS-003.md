# AC-KJS-003

Covers: R-KJS-002
Kind: generated-test

```gherkin
Given tmp_path / "bad.js" holding exactly
  "export function f(a {\n  return fetch(a);\n}\n"
When layout_errors(that path) is called
Then the result is exactly
  ["parse error: SyntaxError: Unexpected token '{'", "forbidden: fetch("]
And a file holding the bytes b"export const s = '\xff';\n" (not UTF-8)
  gives exactly ["parse error: not UTF-8"]
```
