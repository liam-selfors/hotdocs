# AC-LICENSE-010

Covers: R-LICENSE-008
Kind: generated-test

```gherkin
Given a repo_root with VAR-LICENSE-CORPUS-PATH pointing at a corpus
  file whose corpus_version is 4, and a component with files under gen/
When gate_version(repo_root) and scan(component_id, repo_root) are
  both called
Then gate_version returns the same string as the scan result's
  gate_version

Given the corpus file's corpus_version changed to 5
When gate_version(repo_root) is called again
Then it returns a different string than before

Given VAR-LICENSE-CORPUS-PATH unset
When gate_version(repo_root) and scan(component_id, repo_root) are
  both called
Then both report the same gate_version

Given a repo_root with no gen/ directory and a faked cache-manager
  that records every call
When gate_version(repo_root) is called
Then it returns a string and the faked cache-manager was never called
```
