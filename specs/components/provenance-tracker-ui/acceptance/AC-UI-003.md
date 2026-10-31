# AC-UI-003

Covers: R-UI-003
Kind: generated-test

```gherkin
Given a page rendered for a snapshot containing a failing component
  with a non-empty retry_feedback
When index.html is inspected
Then it contains no <form element, no "hotdocs generate" inside any
  executable script element (every script element except the
  id="tracker-snapshot" JSON data block, whose not_ready_reasons are
  copied verbatim from provenance-tracker and may name that command),
  and no href attribute other than ones beginning with "#"
```
