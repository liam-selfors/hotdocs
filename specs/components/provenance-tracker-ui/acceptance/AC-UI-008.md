# AC-UI-008

Covers: R-UI-008
Kind: generated-test

```gherkin
Given comp-foo's node is failing, and its last AttemptRecord's
  requirement_results shows R-FOO-002 as fail
When a developer drills into comp-foo's node
Then its AttemptRecord history is shown along with a retry-feedback
  suggestion naming R-FOO-002, ready to copy — and no control anywhere
  on the page passes it to hotdocs generate automatically
```
