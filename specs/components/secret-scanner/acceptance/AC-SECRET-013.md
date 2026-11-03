# AC-SECRET-013

Covers: R-SECRET-011
Kind: generated-test

```gherkin
Given a repo_root with no secrets
When main(["--repo-root=<repo_root>", "--format=json"]) runs
Then it returns 0 and prints JSON whose flagged is false

Given gen/foo/c.py holding K = "AKIAABCDEFGHIJKLMNOP"
When main(["--repo-root", "<repo_root>", "--format", "text"]) runs
Then it returns 1 and prints text containing "FLAGGED"

Given two files, one clean and one holding that key
When main(["precommit", "--files", "<clean>", "--files=<secret>"])
  runs, and again with only "--files=<clean>"
Then the first returns 1 and the second returns 0

Given a git repository at repo_root with one committed clean file, then
  a new staged file holding the key
When main(["precommit", "--repo-root", "<repo_root>"]) runs, no --files
Then it returns 1

Given --format=bogus, or an unknown argument, or an unknown subcommand,
  or "--repo-root" as the last argument with no value, or
  main(["propose", "--format=json"])
When main runs
Then it returns 2
```
