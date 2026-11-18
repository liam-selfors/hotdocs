# AC-IMPACT-012

Covers: R-IMPACT-010
Kind: generated-test

```gherkin
Given a real git repo whose root holds a lint-clean corpus with comp-foo
  and comp-bar, where comp-bar depends_on comp-foo, and the working
  directory is the repo's specs/ subdirectory
When hotdocs impact --changed comp-foo --format=json runs with no
  --repo-root
Then it exits with code 0 and the report's impacted list contains
  comp-foo with reason "direct", read from the repo root's corpus
```
