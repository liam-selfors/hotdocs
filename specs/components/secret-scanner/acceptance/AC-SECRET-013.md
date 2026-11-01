# AC-SECRET-013

Covers: R-SECRET-011
Kind: generated-test

```gherkin
Given a repo_root whose specs/, gen/, and verification/ hold no
  secrets
When main(["--repo-root=<repo_root>", "--format=json"]) runs
Then it returns 0 and prints JSON whose flagged is false

Given VAR-SECRET-PATTERNS-PATH pointing at a pattern database with
  one high-risk rule whose pattern is "AKIA[0-9A-Z]{16}", and a gen/
  file containing "AKIAABCDEFGHIJKLMNOP"
When main(["--repo-root", "<repo_root>", "--format", "text"]) runs
Then it returns 1 and prints text containing "FLAGGED"

Given two files, one clean and one containing that key
When main(["precommit", "--files", "<clean>", "--files=<secret>"])
  runs
Then it returns 1, and with only "--files=<clean>" it returns 0

Given a git repository at repo_root with one committed clean file,
  then a new staged file containing that key
When main(["precommit", "--repo-root", "<repo_root>"]) runs with no
  --files
Then it returns 1

Given a pattern database rule missing its risk_tier, alongside the
  valid AKIA rule
When main runs the full scan on a gen/ file containing the key
Then it returns 1 and only the valid rule's rule_id appears in the
  JSON matches

Given --format=bogus, or an unknown argument, or an unknown
  subcommand, or "--repo-root" as the last argument with no value
When main runs
Then it returns 2
```
