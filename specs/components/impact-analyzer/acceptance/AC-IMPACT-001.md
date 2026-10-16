# AC-IMPACT-001

Covers: R-IMPACT-001
Kind: compiled

```gherkin
Given a changed spec id for component comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-foo with reason "direct"
```
