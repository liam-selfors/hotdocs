# AC-STYLE-001

Covers: R-STYLE-001
Kind: generated-test

```gherkin
Given the module ui_style and the declared asset at
  Path(ui_style.__file__).parent / "static" / "style.css"
When stylesheet() and style_element() are called
Then stylesheet() equals that file's text read as UTF-8,
  style_element() equals "<style>\n" + stylesheet() + "</style>", and
  "</style" does not occur in stylesheet()
```
