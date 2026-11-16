# AC-VERIFY-014

Covers: R-VERIFY-013
Kind: generated-test

```gherkin
Given two separate repo_root directories, both declaring a component
  with the same slug but different code, verified one after the other
  in the same process
When verify runs against each repo_root in turn
Then each call's interface-drift result and compiled-criterion
  results reflect that call's own repo_root's code, never a module
  cached from the other repo_root's earlier call
```
