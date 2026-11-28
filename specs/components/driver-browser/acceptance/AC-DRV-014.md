# AC-DRV-014

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given a page v.html written under tmp_path holding exactly
  <svg width="100" height="100"><line class="v" x1="50" y1="10" x2="50" y2="90" style="stroke: rgb(1, 2, 3)"></line></svg>
  inside its body
When it is opened and the line is found with css="line.v"
Then attribute("x1") is "50" and style("stroke") is "rgb(1, 2, 3)",
  and
  find(css="line.v").text() raises BrowserError "no element matches css=line.v"
```
