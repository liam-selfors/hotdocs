# AC-UI-003

Covers: R-UI-003
Kind: generated-test

```gherkin
Given the rendered page's source and rendering logic
When inspected for any control that invokes hotdocs merge, a shell
  command, or any other side-effecting action
Then none exists — the page only renders; the only re-run mechanism is
  the developer typing the merge command themselves, outside this page
```
