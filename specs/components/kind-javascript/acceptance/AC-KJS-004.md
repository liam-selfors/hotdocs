# AC-KJS-004

Covers: R-KJS-003
Kind: generated-test

```gherkin
Given tmp_path / "m.js" holding exactly
  "export function beta(x) { return x; }\n"
  "export const alpha = 1;\n"
  "function hidden() { return 2; }\n"
  "export default 3;\n"
When surface(that path) is called
Then the result is exactly {"names": ["alpha", "beta", "default"]}
And surface of a file holding "export function f( {\n" (no parse)
  is exactly {"names": []}
```
