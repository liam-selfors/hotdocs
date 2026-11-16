# AC-IMPACT-009

Covers: R-IMPACT-009
Kind: generated-test

```gherkin
Given comp-foo depends_on comp-bar, declared only in each component's own
  component.md frontmatter, and no corpus-graph.json or other
  precomputed graph artifact exists anywhere in the repo
When hotdocs impact --changed comp-bar runs
Then the report's impacted list contains comp-foo with reason
  "transitive-interface" — computed directly from the component.md files
  present, confirming no precomputed intermediate graph is required
```
