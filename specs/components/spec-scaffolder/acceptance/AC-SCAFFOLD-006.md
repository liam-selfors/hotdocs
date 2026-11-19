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
  with ["component", "new"], with ["kind", "new"] and with ["kind"]
Then each returns 2, stderr's first line starts "usage error: ", no
  traceback is printed, and nothing is written under repo_root

Given a repo_root with a specs/ directory
When main(["component", "new", "my-thing", "--sealed",
  "--repo-root=<repo_root>"]) is called
Then it returns 0, prints "specs/components/my-thing/" to stdout, and
  component.md's sealed line is "sealed: true"

Given a repo_root whose specs/decisions/ holds D4.md
When main(["kind", "new", "sql", "--title", "SQL", "--owners=a, b",
  "--realizes=P-DATA", "--repo-root=<repo_root>"]) is called
Then it returns 0 and prints exactly three lines to stdout,
  "specs/architecture/asset-kind-sql.md", "specs/components/kind-sql/" and
  "specs/decisions/D5.md"; the definition's title line is
  "title: Asset kind SQL" and its owners line "owners: [a, b]"; and
  component.md's realizes line is "realizes: [P-DATA]"

Given that repo_root
When main(["kind", "new", "sql", "--repo-root=<repo_root>"]) is called
  again, and separately main(["kind", "new", "python",
  "--repo-root=<repo_root>"])
Then each returns 1, stderr holds one line starting "error: ", and no
  D6.md appears
```
