# AC-STYLE-004

Covers: R-STYLE-004
Kind: generated-test

```gherkin
Given run = asset_runner("static/style.css")
When run("rule", [selector]) is called for each selector of
  R-STYLE-004's table
Then each result equals that row's declarations as a dict of property to
  value, with its keys in the row's order
```
