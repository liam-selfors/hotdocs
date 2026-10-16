# AC-XMODEL-009

Covers: R-XMODEL-009
Kind: compiled

```gherkin
Given a second model from the same vendor as the canonical pin
When cross-check runs
Then different_vendor is false, and the run is neither blocked nor flagged
  as an error — it's a recorded fact, not a gate
```
