# AC-LINT-041

Covers: R-LINT-035
Kind: generated-test

```gherkin
Given testing.md's clean corpus under repo_root
When main(["--repo-root=<repo_root>", "--format=json"]) runs
Then it returns 0 and prints JSON whose summary.hard_failures is 0

Given that corpus plus testing.md's one-warn edit
When main runs with those arguments, then with "--strict" added
Then it returns 0, then 1

Given that corpus plus testing.md's one-fail edit
When main runs with those arguments
Then it returns 1 and the JSON's findings hold one R-LINT-010 finding

Given any repo_root
When main(["--format=xml"]) runs
Then it returns 2
```
