# AC-UI-006

Covers: R-UI-006
Kind: compiled

```gherkin
Given the built page exists at the configured --out directory and a
  request is made to the serve command's local server for a path other
  than the built page or a file under .hotdocs/tracking/
When the server handles that request
Then it returns 404 — confirming the server returns only the literal
  contents of those two known static sources and computes no response of
  its own
```
