# AC-SCAFFOLD-009

Covers: R-SCAFFOLD-009
Kind: generated-test

```gherkin
Given a repo_root with an empty specs/ directory
When new_capability(repo_root, "order-book", owners=["team-a", "team-b"])
  is called
Then it returns the path specs/product/order-book.md under repo_root, and
  that file is exactly the R-SCAFFOLD-009 layout with id P-ORDER-BOOK,
  title "Order Book" and owners [team-a, team-b]: its first line is
  "---", its third "title: Order Book", and it ends
  "## Purpose\n\nTODO.\n"

Given the same repo_root
When new_capability(repo_root, "order-book") is called again, and
  separately new_capability(repo_root, "Order_Book")
Then the first raises FileExistsError and the second ValueError, the
  file is unchanged, and specs/product/ holds no other file

Given a repo_root with a specs/ directory
When main(["capability", "new", "ledger", "--title", "The Ledger",
  "--repo-root=<repo_root>"]) is called
Then it returns 0, stdout is exactly the two lines
  "specs/product/ledger.md" and "id: P-LEDGER", and the file's title line
  is "title: The Ledger" and its owners line "owners: [unassigned]"

Given that repo_root
When main(["capability", "new", "ledger", "--repo-root=<repo_root>"]) is
  called again, and separately main(["capability", "new"]) and
  main(["capability"])
Then the first returns 1 with one stderr line starting "error: ", and
  the other two return 2 with a first stderr line starting
  "usage error: "
```
