# AC-STYLE-002

Covers: R-STYLE-002
Kind: generated-test

```gherkin
Given run = asset_runner("static/style.css")
When run("tokens", []) and run("rule", [":root"]) are called
Then run("tokens", []) equals R-STYLE-002's table as a dict of token to
  value, with its keys in the table's order, and run("rule", [":root"])
  equals that dict plus "color-scheme": "light dark", its last key being
  "color-scheme"
```
