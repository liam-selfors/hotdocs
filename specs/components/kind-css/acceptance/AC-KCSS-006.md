# AC-KCSS-006

Covers: R-KCSS-005
Kind: generated-test

```gherkin
Given testing.md's s.css and run = asset_runner(<its path>)
When run is called with each entry below
Then run("tokens", []) == {"--c-text": "#1f2328", "--c-bg": "#ffffff",
  "--c-gap": "8px"}, run("tokens", ["dark"]) == {"--c-bg": "#0d1117"},
  run("rule", [".card, .panel"]) == {"padding": "var(--c-gap)",
  "color": "var(--c-text)"}, and run("rule", [".card.tone-ok:hover"])
  == {"border-left": "4px solid green"}
And run("rule", [".card"]) raises AssetError "no rule .card", and
  run("style", []) raises AssetError "no entry style"
And after s.css is rewritten to "a {\n  color: red;\n}\n", the same
  run gives run("rule", ["a"]) == {"color": "red"}, and after it is
  rewritten to "}\n", run("tokens", []) raises AssetError
  "invalid layout: parse error: line 1: unexpected }"
```
