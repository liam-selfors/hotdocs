# AC-LICENSE-010

Covers: R-LICENSE-008
Kind: generated-test

```gherkin
Given a repo_root with VAR_LICENSE_CORPUS_PATH pointing at a corpus
  file whose corpus_version is 4, and a component with files under gen/
When gate_version(repo_root) and scan(component_id, repo_root) are
  both called
Then gate_version returns the same string as the scan result's
  gate_version

Given the corpus file's corpus_version changed to 5, and separately an
  entry added with corpus_version unchanged
When gate_version(repo_root) is called again each time
Then it returns a different string than before each time

Given VAR_LICENSE_CORPUS_PATH unset, then set to a missing file, then
  set to an invalid corpus
When gate_version(repo_root) and scan(component_id, repo_root) are
  both called each time
Then both report the same gate_version each time, and the three
  differ from one another

Given a repo_root with no gen/ directory and a faked cache-manager
  that records every call
When gate_version(repo_root) is called
Then it returns a string and the faked cache-manager was never called
```
