# AC-SCAFFOLD-006

Covers: R-SCAFFOLD-006
Kind: generated-test

```gherkin
Given a repo_root with an empty specs/decisions/ directory
When main(["decision", "new", "First call", "--owners=a, b",
  "--repo-root=<repo_root>"]) is called
Then it returns 0, prints "specs/decisions/D1.md" to stdout, and D1.md's
  owners line is "owners: [a, b]"

Given that repo_root
When main(["decision", "ratify", "D9", "--repo-root", "<repo_root>"]) is
  called
Then it returns 1 and stderr holds one line starting "error: "

Given any repo_root
When main is called with ["decision", "new", "x", "--bogus"], with
  ["decision", "new", "x", "--owners"], with ["decision", "frobnicate"],
  and with ["component", "new"]
Then each returns 2, stderr's first line starts "usage error: ", no
  traceback is printed, and nothing is written under repo_root

Given a repo_root with a specs/ directory
When main(["component", "new", "my-thing", "--sealed",
  "--repo-root=<repo_root>"]) is called
Then it returns 0, prints "specs/components/my-thing/" to stdout, and
  component.md's sealed line is "sealed: true"
```
