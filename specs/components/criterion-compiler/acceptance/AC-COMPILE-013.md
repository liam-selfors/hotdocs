# AC-COMPILE-013

Covers: R-COMPILE-012
Kind: generated-test

```gherkin
Given a criterion whose Given/When/Then text only ever uses literal-only
  steps (no step references a function or type), parsed independently of
  any component's acceptance/ directory
When compile_criterion is called with no interface surface at all
Then compilation succeeds and the emitted source matches what compile
  would emit for the same criterion content against an empty surface

Given a second criterion, parsed the same way, whose When step invokes
  a named function
When compile_criterion is called with no interface surface
Then compilation fails with a located, specific error naming the
  unresolved function -- never silently skipped for lack of a surface
```
