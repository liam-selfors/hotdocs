# AC-STYLE-005

Covers: R-STYLE-004
Kind: generated-test

```gherkin
Given testing.md's page p.html opened with browser.open
When the computed styles are read
Then page.find(css="li.node").style("border-left-color") is
  "rgb(209, 36, 47)", its style("border-top-color") is
  "rgb(209, 217, 224)", its style("border-left-width") is "4px",
  page.find(css="body").style("background-color") is
  "rgb(255, 255, 255)", and page.console_errors() is []
And with p.html opened with color_scheme="dark", the li's
  style("border-left-color") is "rgb(248, 81, 73)" and the body's
  style("background-color") is "rgb(13, 17, 23)"
```
