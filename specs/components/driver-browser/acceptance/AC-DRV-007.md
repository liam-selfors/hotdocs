# AC-DRV-007

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given a page titled "Keys" whose inline script writes into <p id="out">
  the last event it saw: "key:<key>" for each keydown on the document,
  "dbl" on a dblclick of #d, "hover" on mouseenter of #h, "sel:<value>"
  on change of <select id="s"> (options a and b), "wheel" on a wheel
  event over #w, "drag:<dx>" on a mouseup after a mousedown on #g
  giving the pointer's x movement, "shift" on a click of #m with Shift
  held, "chk:<checked>" on change of checkbox #k, and
  "size:<innerWidth>" on resize
When it is opened and, one at a time, page.press("Escape"),
  find(css="#d").dblclick(), find(css="#h").hover(),
  find(css="#s").select("b"), find(css="#w").wheel(0, 50),
  find(css="#g").drag_by(30, 0), find(css="#m").click(modifiers=["Shift"]),
  find(css="#k").check(), find(css="#k").uncheck() and set_size(500, 400)
  are called
Then after each, find(css="#out").text() is, in turn, "key:Escape",
  "dbl", "hover", "sel:b", "wheel", "drag:30", "shift", "chk:true",
  "chk:false" and "size:500"; and title() is "Keys" and url() ends with
  the page's file name
```
