# AC-DRV-003

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given a page whose inline script throws Error("boom") on load, calls
  alert("hi") when a button "Warn" is clicked, and offers a download
  "out.svg" when a button "Export" is clicked
When it is opened and both buttons are clicked
Then console_errors() is ["Error: boom"], dialogs() is ["hi"], and
  downloads() is one path named out.svg under tmp_path/downloads

When screenshot("home") is called
Then it returns tmp_path/screenshots/home.png, a file starting with
  the PNG signature

When open("https://example.com/") is called
Then BrowserError is raised with message
  "only file paths and loopback URLs can be opened: https://example.com/"
```
