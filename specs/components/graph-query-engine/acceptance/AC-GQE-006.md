# AC-GQE-006

Covers: R-GQE-006
Kind: compiled

```gherkin
Given a repo root with a real spec corpus
When load_views runs and component_size is queried
Then every component's word_count matches spec-linter's own
  previously-verified component_doc_words value exactly
```
