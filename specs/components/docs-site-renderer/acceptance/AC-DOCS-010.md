# AC-DOCS-010

Covers: R-DOCS-009
Kind: generated-test

```gherkin
Given run = asset_runner("static/app.js"),
  nodes = [{"id": "comp-Alpha", "type": "component"},
           {"id": "comp-beta", "type": "component"},
           {"id": "P-ALPHA-CAP", "type": "capability"}]
  and edges = [{"from": "comp-Alpha", "to": "comp-beta", "kind": "depends_on"},
               {"from": "comp-Alpha", "to": "P-ALPHA-CAP", "kind": "realizes"},
               {"from": "comp-beta", "to": "missing", "kind": "depends_on"}]
When run("filterGraph", [nodes, edges, <query>]) is called
Then it returns exactly {"hiddenNodes": H, "hiddenEdges": E} with
  | query       | H comp-Alpha | H comp-beta | H P-ALPHA-CAP | E                  |
  | "ALPHA"     | false        | true        | false         | [true, false, true] |
  | "comp-"     | false        | false       | true          | [false, true, true] |
  | ""          | false        | false       | false         | [false, false, true] |
  | "zzz"       | true         | true        | true          | [true, true, true]  |
  | "component" | true         | true        | true          | [true, true, true]  |
  | " alpha"    | true         | true        | true          | [true, true, true]  |
  where H maps exactly those three ids to the given booleans

Given the same run
When run("filterGraph", [[], [], "a"]) is called
Then it returns {"hiddenNodes": {}, "hiddenEdges": []}
```
