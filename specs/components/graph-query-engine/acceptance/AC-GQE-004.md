# AC-GQE-004

Covers: R-GQE-004
Kind: generated-test

```gherkin
Given a component whose Purpose section spans multiple lines
When load_views runs and component_context is queried for it
Then purpose contains the full multi-line text, not an empty string
```
