# AC-SECRET-002

Covers: R-SECRET-002
Kind: generated-test

```gherkin
Given a full scan with at least one match
When scan(repo_root) and main(["--repo-root", <repo_root>, "--format=json"]) run
Then the result's flagged is true, and main exits 1
```
