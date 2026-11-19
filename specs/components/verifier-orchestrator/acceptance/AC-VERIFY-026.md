# AC-VERIFY-026

Covers: R-VERIFY-006
Kind: generated-test

```gherkin
Given these three Python literals
  NOTE = "a === b && c"
  SCRIPT = "function f(a, b) { var s = 'it\\'s === no'; /* a && b */ return a === b; // c || d\n}"
  PAGE = "<p>a === b</p><script>let t = x + 1 - -y;</script>"
  and an unsealed comp-qux whose gen/qux/qux.py is exactly
  f"NOTE = {NOTE!r}\n\n\ndef script():\n    return {SCRIPT!r}\n\n\ndef page():\n    return {PAGE!r}\n"
  and one cached generated test asserting qux.script() == SCRIPT
When verify runs
Then that criterion is pass and mutation_score == 1 / 3:
  SCRIPT's one site is the === outside its string and comments, killed;
  PAGE's two are the + after x and the - after 1 inside <script>, both
  surviving; NOTE is not JavaScript

Given the same component and one cached generated test asserting only
  that "function" is in qux.script()
When verify runs
Then that criterion is pass, mutation_score is 0.0 and overall is
  "fail"
```
