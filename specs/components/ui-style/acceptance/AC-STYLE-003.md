# AC-STYLE-003

Covers: R-STYLE-003
Kind: generated-test

```gherkin
Given run = asset_runner("static/style.css")
When run("tokens", ["dark"]) and run("contrast", ...) are called
Then run("tokens", ["dark"]) equals R-STYLE-003's table as a dict, with
  its keys in the table's order
And for each of "--color-text", "--color-text-muted" and
  "--color-accent", against each of "--color-bg" and "--color-surface",
  run("contrast", [a, b]) and run("contrast", [a, b, "dark"]) are each
  at least 4.5
And for each of "--color-focus", "--color-ok", "--color-warn",
  "--color-fail", "--color-neutral", "--color-edge-depends-on",
  "--color-edge-realizes" and "--color-edge-other", against each of "--color-bg"
  and "--color-surface", both are at least 3
```
