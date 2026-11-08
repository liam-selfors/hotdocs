# AC-CLI-004

Covers: R-CLI-004
Kind: generated-test

```gherkin
Given any project
When main([]), main(["--help"]), main(["-h"]), main(["help"]) are called
Then each returns 0 and prints "hotdocs 0.1.0" and every verb of the table, "init" included, with its summary

Given main(["--version"])
When called
Then it prints "hotdocs 0.1.0" and returns 0

Given main(["frobnicate"])
When called
Then it returns 2 and stderr holds "unknown verb: frobnicate" and the verb list

Given a project and an empty fake tool root, neither with gen/spec-linter,
  then a project whose fake has no main
When main(["lint"], tool_root=<fake tool root>) is called
Then each returns 2; the first message names "gen/spec-linter/spec_linter.py"
```
