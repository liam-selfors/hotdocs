# AC-CLI-004

Covers: R-CLI-004
Kind: generated-test

```gherkin
Given any project
When run([]), run(["--help"]), run(["-h"]), run(["help"]) are called
Then each returns 0 and prints "hotdocs 0.1.0" and every verb of the table, "init" included, with its summary

Given run(["--version"])
When called
Then it prints "hotdocs 0.1.0" and returns 0

Given run(["frobnicate"])
When called
Then it returns 2 and stderr holds "unknown verb: frobnicate" and the verb list

Given a project and an empty fake tool root, neither with gen/spec-linter,
  then a project whose fake has no main
When run(["lint"], tool_root=<fake tool root>) is called
Then each returns 2; the first message names "gen/spec-linter/spec_linter.py"
```
