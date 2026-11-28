# AC-DRV-012

Covers: R-DRV-002
Kind: generated-test

The page `s.html`, written under `tmp_path` exactly as:

```html
<!doctype html><html><head><style>
:root { --c: #ff0000; }
p { color: var(--c); margin-top: 1.5em; font-size: 10px; }
@media (prefers-color-scheme: dark) { p { color: #00ff00; } }
</style></head><body><p>x</p></body></html>
```

```gherkin
Given s.html
When it is opened with open_session's open, once as it is and once
  with color_scheme="dark"
Then, opened as it is, find(css="p").style("color") is
  "rgb(255, 0, 0)", style("margin-top") is "15px" and
  find(css="html").style("--c") is "#ff0000"
And, opened with color_scheme="dark", find(css="p").style("color") is
  "rgb(0, 255, 0)"
And open(<s.html>, color_scheme="blue") raises BrowserError
  "color_scheme is light or dark: blue"
```
