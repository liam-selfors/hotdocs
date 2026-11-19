# AC-KJS-002

Covers: R-KJS-002
Kind: generated-test

```gherkin
Given tmp_path / "app.js" holding exactly
  "// import x from 'y'; fetch(\n"
  "const s = \"require('fs') and new WebSocket(u)\";\n"
  "export function f(a) { return a + 1; }\n"
When layout_errors(that path) is called
Then the result is [] (forbidden words only inside a comment and a string)
And the same call on a file holding exactly
  "import x from './x.js';\n"
  "export function g(u) { fetch(u); require (u); return new XMLHttpRequest(); }\n"
  "export const h = () => import('./y.js') && new WebSocket('ws://a');\n"
returns exactly ["forbidden: import", "forbidden: fetch(",
  "forbidden: require(", "forbidden: XMLHttpRequest",
  "forbidden: import", "forbidden: WebSocket"]
```
