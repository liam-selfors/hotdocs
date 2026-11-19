# AC-KJS-011

Covers: R-KJS-008
Kind: generated-test

```gherkin
Given tmp_path / "a.js" holding exactly
  "export function f(a, b) {\r\n  return a - b < 0;\r\n}\r\n"
And sites = strength_sites(that path), whose descriptions are exactly
  ["2: - -> +", "2: < -> >="]
When apply_site(that path, sites[1]) is called
Then the file's bytes are exactly
  b"export function f(a, b) {\r\n  return a - b >= 0;\r\n}\r\n"
And apply_site with a site whose token does not match the text at its
  offset, e.g. dict(sites[0], token="*"), raises ValueError and leaves
  the file unchanged
```
