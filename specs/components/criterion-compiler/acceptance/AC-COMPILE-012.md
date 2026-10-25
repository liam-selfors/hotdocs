# AC-COMPILE-012

Covers: R-COMPILE-007
Kind: generated-test

```gherkin
Given a criterion with a Given step binding a fixture "user_id" to "u1",
  followed by a When step whose args include both a bare reference to
  user_id as a whole value and nested inside an object literal (e.g.
  {"owner": user_id})
When compile-criteria runs
Then compilation succeeds and both positions are resolved to the literal
  "u1" in the emitted test, with no runtime lookup or evaluation in the
  generated code

Given a criterion whose step contains "user_id + 1" (an operator applied
  to a bound fixture) in a literal position
When compile-criteria runs
Then compilation fails with a specific, located error naming the
  expression as not a literal — never silently evaluated and never
  silently treated as a literal string

Given a criterion whose step references "user_id.id" (field access on a
  bound fixture) in a literal position
When compile-criteria runs
Then compilation fails with a specific, located error — field/index
  access is rejected the same as any other expression, not specially
  allowed

Given a criterion whose step references a bare identifier "does_not_exist"
  that was never bound by any earlier Given step in the same criterion
When compile-criteria runs
Then compilation fails with a specific, located unresolved-reference
  error — never silently treated as a literal string
```
