# AC-AUTHOR-017

Covers: R-AUTHOR-016
Kind: generated-test

```gherkin
Given a CriterionBundle-shaped object (plain object, not a dict) that
  has no dependency_interfaces attribute at all
When author_test is called with that bundle
Then it does not raise AttributeError and completes, treating
  dependency_interfaces as empty

Given a dict-shaped bundle missing the "dependency_interfaces" key
When author_test is called with that bundle
Then it does not raise KeyError and completes, treating
  dependency_interfaces as empty
```
