# AC-KCSS-010

Covers: R-KCSS-008
Kind: generated-test

```gherkin
Given testing.md's s.css and its fourth strength site,
  {"description": "8: --c-bg removed", "offset": 118, "end": 134,
  "property": "--c-bg"}
When apply_site is called with it
Then the file's text is the original with exactly the characters 118
  to 133 removed, so its eighth line is four spaces, and
  apply_site(<the same file>, {"description": "x", "offset": 0,
  "end": 3, "property": "color"}) raises ValueError and leaves the
  file unchanged
```
