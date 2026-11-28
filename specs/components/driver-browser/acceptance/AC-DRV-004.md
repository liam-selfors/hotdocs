# AC-DRV-004

Covers: R-DRV-003
Kind: generated-test

```gherkin
Given a page holding <img src="https://example.com/x.png"> and
  <img src="pic.png"> with pic.png beside it
When it is opened
Then blocked_requests() is ["https://example.com/x.png"]

Given a page served by a loopback server, whose script writes
  navigator.language and Intl.DateTimeFormat().resolvedOptions().timeZone
  into the page
When it is opened by its http://127.0.0.1:<port>/ URL
Then blocked_requests() is [] and the page shows "en-US" and "UTC"
```
