# AC-DRV-006

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given a page holding <input id="n" value="7">, <a id="l" href="x.html"
  data-k="v">Link</a>, <input id="c" type="checkbox" checked>, a
  <div id="box" style="position:absolute;left:10px;top:20px;width:30px;height:40px"></div>,
  and <ul><li>one</li><li>two</li><li>three</li></ul>
When it is opened at width 400 and height 300
Then find(css="#n").value() is "7", find(css="#l").attribute("data-k")
  is "v" and attribute("missing") is None, find(css="#c").checked() is
  True, find(css="#box").box() is {"x": 10, "y": 20, "width": 30,
  "height": 40}, find(css="li").nth(1).text() is "two",
  find(css="ul").find(text="three").text() is "three", and
  find(css="li").text() raises BrowserError with message
  "3 elements match css=li"
```
