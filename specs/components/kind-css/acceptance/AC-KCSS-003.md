# AC-KCSS-003

Covers: R-KCSS-002
Kind: generated-test

Files, every line ending in `\n`:

- `forbid.css`: `a {`, `  background: url(x.png);`,
  `  width: expression(1);`, `}`, `/* </style> */`
- `quoted.css`: `a { content: "url(x)"; }`
- `both.css`: `}`, `a { background: URL(x); }`

```gherkin
Given those files
When layout_errors is called on each
Then forbid.css gives exactly ["forbidden: url(",
  "forbidden: expression(", "forbidden: </style"], quoted.css gives
  [], and both.css gives exactly
  ["parse error: line 1: unexpected }", "forbidden: url("]
```
