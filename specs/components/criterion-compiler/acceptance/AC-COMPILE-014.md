# AC-COMPILE-014

Covers: R-COMPILE-013
Kind: generated-test

```gherkin
Given a component whose interface declares a function and whose
  acceptance criterion invokes that function in a When step
When the criterion is compiled
Then the emitted source contains a single top-level import of the
  target module, by the component's underscored slug, and every call
  to the declared function in the emitted test body is qualified with
  that module name rather than called as a bare global

Given a component whose acceptance criteria only ever use literal-only
  steps, with no When-invoke and no typed Given step
When the criteria are compiled
Then the emitted source contains no import statement for the target
  module at all
```
