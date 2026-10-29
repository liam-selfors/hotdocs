# AC-TRACK-011

Covers: R-TRACK-011
Kind: generated-test

```gherkin
Given two separate repo_root directories, each with its own fake
  impact-analyzer module matching the real, documented
  compute_blast_radius signature and return shape exactly (never a
  duck-typed stand-in that answers truthy to any attribute lookup --
  that would mask, not test, a real precondition check), each
  returning a different, distinctive list of impacted component ids
  with no precondition error
When check_readiness is called once against each repo_root in the
  same process, in either order
Then each call's result reflects that call's own repo_root's fake,
  never the other repo_root's fake or any real impact-analyzer module
```
