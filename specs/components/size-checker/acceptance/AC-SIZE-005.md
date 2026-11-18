# AC-SIZE-005

Covers: R-SIZE-001
Kind: generated-test

```gherkin
Given a component whose interface/cli.md's first fenced block holds
  three non-blank lines, one of them ending in a backslash that joins
  it to a fourth line, and one blank line; whose interface/library.md's
  first fenced block holds five signature lines of the form
  "name(args) -> T" and one prose line; and whose interface/data/
  holds three files
When check(repo_root) runs
Then it reports exactly one R-SIZE-001 finding for that component, a
  warn whose message names interface_surface and the value 11
```
