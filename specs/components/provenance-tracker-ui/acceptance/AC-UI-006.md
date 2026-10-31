# AC-UI-006

Covers: R-UI-006
Kind: generated-test

```gherkin
Given a rendered index.html
When it is inspected for anything requiring a server
Then it contains no "fetch(", no "XMLHttpRequest", no "http://", and
  no "https://", and the module exposes no serve function and main
  treats a "serve" subcommand as a usage error returning 2
```
