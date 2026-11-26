# AC-GQE-011

Covers: R-GQE-009
Kind: generated-test

```gherkin
Given the fixture corpus of specs/architecture/graph-query-engine-fixture.md
  written under a temporary repo_root
When load_views runs and bundle_size is queried
Then foo's generator_words is 20 and criterion_words_max is 16, and
  bar's are 2 and 0

Given that corpus, with foo's component.md gaining the final lines
  "", "## Rationale", "", "Old reasons here." and bar's gaining "",
  "## Purpose", "", "Bar holds data.", "", "## Change log", "",
  "- D1 added it."
When load_views runs and bundle_size is queried
Then foo's generator_words is 24 and bar's is 6
```
