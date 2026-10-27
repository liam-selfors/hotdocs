# AC-GEN-015

Covers: R-GEN-014
Kind: generated-test

```gherkin
Given a repo_root whose gen/cache-manager/cache_manager.py defines a
  real dataclass, and an implementation that loads cache-manager
  dynamically, per call, from that repo_root
When generate is called twice in the same process with two different
  repo_root values, each defining its own cache-manager
Then neither call raises (cache-manager's dataclasses resolve cleanly
  in both), and each call's cache-manager module reflects its own
  repo_root's code, not the other call's
```
