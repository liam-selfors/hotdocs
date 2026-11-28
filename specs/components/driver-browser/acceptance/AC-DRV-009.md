# AC-DRV-009

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given a page holding buttons "Add" and "Add more", inputs labelled
  "Query" and "Query text", list items "alpha" and "alphabet", a
  <div id="late"> whose inline script adds a button "Late" inside it
  one second after load, a <div id="g"> that writes "drag:<dx>,<dy>"
  into <p id="out"> on mouseup after a mousedown on it, and a body 2000
  pixels tall, opened at width 400 and height 300
When find(role="button", name="Add").click(), find(label="Query").fill("q"),
  find(text="alpha").text(), find(role="button", name="Late").click(),
  find(css="#g").drag_by(0, 30) and screenshot("full") are called
Then none raises; find(css="#out").text() is "drag:0,30"; and the PNG
  written for "full" has a height, read from its IHDR header, of at
  least 2000 pixels
```
