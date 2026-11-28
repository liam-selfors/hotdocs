# AC-DRV-013

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given two pages a.html and b.html written under tmp_path, each a
  complete HTML document holding one <p> with its own name
When a session opens a.html, then b.html, and close() is called twice
Then <tmp_path>/screenshots/ holds exactly final-1.png and final-2.png,
  each file's first eight bytes are b"\x89PNG\r\n\x1a\n", and the second
  close() raises nothing and adds no file
```
