# AC-DRV-010

Covers: R-DRV-003
Kind: generated-test

```gherkin
Given tmp_path/site/page.html holding <img src="../outside.png">, and
  tmp_path/outside.png
When tmp_path/site/page.html is opened
Then blocked_requests() is [the file:// URL of tmp_path/outside.png]

Given a page with no external reference whose inline script calls
  console.log("info") and console.error("bad")
When it is opened
Then console_errors() is ["bad"] and blocked_requests() is []

When open("http://example.com/") is called, and separately
  open("ftp://127.0.0.1/x")
Then each raises BrowserError with message
  "only file paths and loopback URLs can be opened: <the URL>"
```
