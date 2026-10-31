# AC-GEN-019

Covers: R-GEN-018
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle and a mock model that records what it
  was sent
When generate is called with that bundle
Then the mock model's recorded input instructs it that any dynamic
  dependency load must resolve from repo_root, never via a bare
  import, a sys.modules lookup, or a __file__-relative path
```
