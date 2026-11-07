# AC-INIT-008

Covers: R-INIT-008
Kind: generated-test

```gherkin
Given an empty directory and a fake tool root
When main(["<dir>", "--yes"]) is called
Then .secret-allowlist.json parses to version 1 with exactly the one public-constant entry,
  specs/decisions/D1.md exists with status "ratified" and allowlist_sha256 equal to "sha256:" plus the
  SHA-256 hex of the allowlist file's bytes, and output_fn received "specs/decisions/D1.md: created"

Given a directory whose specs/decisions holds D3.md and D12.md
When init runs
Then D13.md is the sealing decision and D3.md and D12.md are unchanged

Given a directory with an existing .secret-allowlist.json
When init runs
Then that file is unchanged, no D*.md file appears in specs/decisions, and no
  "specs/decisions/D" line is printed (the directory and .gitkeep lines of R-INIT-001 still are)
```
