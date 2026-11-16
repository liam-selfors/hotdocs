# AC-LICENSE-011

Covers: R-LICENSE-009
Kind: generated-test

```gherkin
Given a repo_root whose corpus (via VAR_LICENSE_CORPUS_PATH) shares no
  k-grams with the files under gen/foo/ (comp-foo's directory)
When main(["comp-foo", "--repo-root=<repo_root>", "--format=json"])
  runs
Then it returns 0 and prints JSON whose blocked is false

Given the same repo_root
When main(["comp-foo", "--repo-root", "<repo_root>", "--format",
  "text"]) runs
Then it returns 0 and prints text containing "similarity_score"

Given a corpus that the files under gen/foo/ copy verbatim, at or above
  the block threshold
When main runs for comp-foo
Then it returns 1

Given VAR_LICENSE_CORPUS_PATH unset
When main(["comp-foo", "--repo-root=<repo_root>", "--format=text"])
  runs, and again with "--format=json"
Then both return 0, the text output contains "NOT EVALUATED:
  no-reference-corpus", and the JSON has evaluated false

Given VAR_LICENSE_CORPUS_PATH naming a missing file
When main runs for comp-foo
Then it returns 1 and the text output contains "NOT EVALUATED:
  corpus-unreadable"

Given no component id, or --format=bogus, or an unknown argument, or
  "--repo-root" as the last argument with no value
When main runs
Then it returns 2
```
