# AC-SCAFFOLD-005

Covers: R-SCAFFOLD-005
Kind: generated-test

```gherkin
Given an empty repo_root with a specs/ directory
When new_component(repo_root, "order-book", depends_on=["comp-ledger"],
  realizes=["P-TRADING"]) is called
Then it returns the path specs/components/order-book under repo_root;
  that directory holds component.md, constraints.md and the four
  directories each with an empty .gitkeep; component.md is exactly the
  R-SCAFFOLD-005 layout with title "Order Book", owners [unassigned],
  depends_on [comp-ledger], realizes [P-TRADING] and sealed false; and
  constraints.md is exactly "# Order Book — Non-Functional
  Constraints\n\n- TODO.\n"

Given the same repo_root
When new_component(repo_root, "order-book") is called again, and
  separately new_component(repo_root, "Order_Book") is called
Then the first raises FileExistsError and the second ValueError, and no
  other directory appears under specs/components/
```
