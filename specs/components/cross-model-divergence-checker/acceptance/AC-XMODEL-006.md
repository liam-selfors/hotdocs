# AC-XMODEL-006

Covers: R-XMODEL-006
Kind: compiled

```gherkin
Given a second candidate whose verdict is fail, in divergence mode
When cross-check runs
Then the result is logged as a second-model capability gap, diverged is
  false (not evaluated), and the result is not merge-blocking (exit code 0)
```
