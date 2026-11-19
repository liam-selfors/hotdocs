# AC-VERIFY-014

Covers: R-VERIFY-013
Kind: generated-test

```gherkin
Given two repo_root directories, each with a component of the same slug
  but different code
When verify runs against each in turn in the same process
Then each call's interface_drift and compiled-criterion results reflect
  its own repo_root's code
```
