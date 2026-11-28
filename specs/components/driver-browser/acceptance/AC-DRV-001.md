# AC-DRV-001

Covers: R-DRV-001
Kind: generated-test

```gherkin
Given the shared environment
When provision is called on it twice
Then both reports have ok true, lockfile_sha256 None, the same versions
  whose "playwright" is "1.64.1" and whose "chromium" is a non-empty
  string, and the second call takes under 30 seconds
```
