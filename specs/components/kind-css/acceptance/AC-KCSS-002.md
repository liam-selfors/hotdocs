# AC-KCSS-002

Covers: R-KCSS-002
Kind: generated-test

Each file below is written to its own path under `tmp_path`, exactly
as shown, every line ending in `\n`.

| File | Text | `layout_errors` |
| --- | --- | --- |
| `ok.css` | `a {` / `  color: red;` / `}` | `[]` |
| `close.css` | `a { color: red; }` / `}` | `["parse error: line 2: unexpected }"]` |
| `open.css` | `a {` / `  color: red;` | `["parse error: line 1: unclosed {"]` |
| `colon.css` | `a {` / `  color red;` / `}` | `["parse error: line 2: expected :"]` |
| `import.css` | `@import "x.css";` | `["parse error: line 1: at-rule @import is not allowed"]` |
| `font.css` | `@font-face {` / `}` | `["parse error: line 1: at-rule @font-face is not allowed"]` |
| `media.css` | `@media (x) {` / `  @media (y) {` / `  }` / `}` | `["parse error: line 2: @media inside @media"]` |
| `nest.css` | `a {` / `  b { color: red; }` / `}` | `["parse error: line 2: unexpected {"]` |
| `semi.css` | `a;` | `["parse error: line 1: unexpected ;"]` |

(`/` separates lines.) And `bad.css`, written with `write_bytes` as
`b"a { color: \xff; }\n"`.

```gherkin
Given those files
When layout_errors is called on each
Then each result is exactly the list its row gives, and bad.css gives
  exactly ["parse error: not UTF-8"]
```
