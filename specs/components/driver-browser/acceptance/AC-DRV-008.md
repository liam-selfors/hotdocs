# AC-DRV-008

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given a page holding <label for="q">Query</label><input id="q">,
  <span data-testid="badge">New</span> and <h2>Title</h2>, written as
  tmp_path/sub/page.html
When open("sub/page.html") is called with the relative path
Then find(label="Query").fill("abc") makes find(css="#q").value()
  "abc", find(test_id="badge").text() is "New", and
  find(role="heading").text() is "Title"

When open("missing.html") is called
Then BrowserError is raised with message
  "no such file: <tmp_path>/missing.html"
```
