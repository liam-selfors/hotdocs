# AC-KCSS-008

Covers: R-KCSS-007
Kind: generated-test

```gherkin
Given testing.md's s.css
When strength_sites is called on it
Then the result is exactly
  [{"description": "2: --c-text removed", "offset": 10, "end": 28, "property": "--c-text"},
   {"description": "3: --c-bg removed", "offset": 31, "end": 47, "property": "--c-bg"},
   {"description": "4: --c-gap removed", "offset": 50, "end": 63, "property": "--c-gap"},
   {"description": "8: --c-bg removed", "offset": 118, "end": 134, "property": "--c-bg"},
   {"description": "13: padding removed", "offset": 159, "end": 181, "property": "padding"},
   {"description": "14: color removed", "offset": 184, "end": 205, "property": "color"},
   {"description": "16: border-left removed", "offset": 230, "end": 261, "property": "border-left"}]
And testing.md's close.css gives []
```
