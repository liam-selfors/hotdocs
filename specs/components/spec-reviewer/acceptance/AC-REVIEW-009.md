# AC-REVIEW-009

Covers: R-REVIEW-003
Kind: generated-test

```gherkin
Given testing.md's synthetic corpus plus a dependent component comp-baz
  (depends_on [comp-foo]) built the same way, and these words: foo's
  interface/library.md gains the line "Returns `dep_word`."; the
  glossary's Foo entry ends "kept in `glossed_word`."; baz's
  interface/library.md gains "Returns `iface_word`."; and AC-BAZ-001's
  Then step names `dep_word`, `glossed_word`, `iface_word`,
  `nowhere_word` and `seen<x>` while its Given step names `given_word`
  and its requirement text names `seen`
When check(["comp-baz"], repo_root) runs with no model
Then AC-BAZ-001's invisible_reference findings have exactly one token,
  "nowhere_word"
```
