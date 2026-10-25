# AC-MERGE-020

Covers: R-MERGE-005
Kind: compiled

```gherkin
Given a mock generator that returns model_call_error on its one call
When run_merge is called
Then generator is called exactly once — never a second time — and the
  component is blocked with a reason distinguishing "no candidate was
  ever produced" from a verification failure
```
