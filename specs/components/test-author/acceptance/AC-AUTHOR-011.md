# AC-AUTHOR-011

Covers: R-AUTHOR-011
Kind: generated-test

```gherkin
Given a bundle whose dependency_interfaces contains one entry for
  comp-bar with distinctive interface text naming a function
  "do_the_thing(x: int, y: str) -> SomeResult"
When author_test builds its prompt
Then the prompt sent to the model contains that exact dependency
  interface text and an instruction that any fake written for a
  dependency must match its real documented signature and return
  shape, never inventing one

Given a bundle whose dependency_interfaces is empty
When author_test builds its prompt
Then the prompt still builds successfully with no dependency-interface
  section claiming a dependency that does not exist
```
