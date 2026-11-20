# AC-INIT-008

Covers: R-INIT-008
Kind: generated-test

```gherkin
Given an empty directory and a fake tool root
When run(["<dir>", "--yes"]) is called
Then .secret-allowlist.json's bytes equal json.dumps({"version": 1, "entries": []}, indent=2) plus a newline,
  and specs/decisions holds only .gitkeep

Given a directory with an existing .secret-allowlist.json
When init runs
Then that file is unchanged and output_fn received ".secret-allowlist.json: skipped (exists)"
```
