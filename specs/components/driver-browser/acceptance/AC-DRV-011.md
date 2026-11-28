# AC-DRV-011

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given a page holding <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=">
  and a button "Export" whose click offers a download "out.svg"
When it is opened, Export is clicked, downloads() is called twice,
  and screenshot("a") then screenshot("b") are called
Then blocked_requests() is [], both downloads() calls return the same
  one path, and both tmp_path/screenshots/a.png and b.png exist
```
