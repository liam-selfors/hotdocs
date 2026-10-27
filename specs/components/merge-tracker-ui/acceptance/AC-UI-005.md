# AC-UI-005

Covers: R-UI-005
Kind: generated-test

```gherkin
Given a repo_root with no .hotdocs/tracking/ directory at all
When the page loads
Then it renders a clear "no attempts recorded yet" state, not an error
  and not a blank page
```
