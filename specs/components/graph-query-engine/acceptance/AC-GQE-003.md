# AC-GQE-003

Covers: R-GQE-003
Kind: compiled

```gherkin
Given a repo root with a real spec corpus
When load_views runs and component_docs is queried
Then its row count equals the real component count, and a known
  component's own frontmatter fields and body text are both present
```
