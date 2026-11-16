# AC-AUTHOR-016

Covers: R-AUTHOR-012
Kind: generated-test

```gherkin
Given any bundle
When author_test builds its prompt
Then the prompt states that status must be exactly one of draft,
  ratified, or deprecated, that the required-frontmatter rule applies
  to VAR-*.md and decision D<N>.md files as well as component.md, and
  that every requirements/ file in a synthetic fixture needs a
  matching acceptance/ file covering it for every component the
  fixture constructs
```
