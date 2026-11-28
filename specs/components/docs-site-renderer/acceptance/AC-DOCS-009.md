# AC-DOCS-009

Covers: R-DOCS-008
Kind: generated-test

```gherkin
Given run = asset_runner("static/app.js"),
  nodes = [{"id": "P-A", "type": "capability"},
           {"id": "VAR-X", "type": "var"},
           {"id": "comp-a", "type": "component"},
           {"id": "P-B", "type": "capability"},
           {"id": "comp-b", "type": "component"},
           {"id": "comp-c", "type": "component"},
           {"id": "zz", "type": "glossary"}]
  and edges = [{"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
               {"from": "comp-a", "to": "P-A", "kind": "realizes"},
               {"from": "comp-b", "to": "VAR-X", "kind": "uses_var"},
               {"from": "comp-c", "to": "gone", "kind": "depends_on"},
               {"from": "gone", "to": "comp-c", "kind": "realizes"},
               {"from": "zz", "to": "P-B", "kind": "mentions"}]
When run("layoutGraph", [nodes, edges]) is called
Then it returns exactly {"width": 1100, "height": 180, "nodes": N, "edges": E}
  where N lists, in this order, {"id", "x", "y", "labelX", "labelY"}:
  | id     | x   | y   | labelX | labelY |
  | P-A    | 120 | 30  | 132    | 34     |
  | VAR-X  | 640 | 30  | 652    | 34     |
  | comp-a | 380 | 30  | 392    | 34     |
  | P-B    | 120 | 70  | 132    | 74     |
  | comp-b | 380 | 70  | 392    | 74     |
  | comp-c | 380 | 110 | 392    | 114    |
  | zz     | 900 | 30  | 912    | 34     |
  and E lists, in this order, {"index", "from", "to", "x1", "y1", "x2", "y2", "class"}:
  | index | from   | to    | x1  | y1 | x2  | y2 | class             |
  | 0     | comp-a | comp-b| 380 | 30 | 380 | 70 | "edge-depends-on" |
  | 1     | comp-a | P-A   | 380 | 30 | 120 | 30 | "edge-realizes"   |
  | 2     | comp-b | VAR-X | 380 | 70 | 640 | 30 | "edge-other"      |
  | 5     | zz     | P-B   | 900 | 30 | 120 | 70 | "edge-other"      |

Given the same run
When run("layoutGraph", [[], []]) is called
Then it returns {"width": 1100, "height": 100, "nodes": [], "edges": []}

Given the same run
When run("layoutGraph", [[{"id": "v", "type": "var"}],
  [{"from": "v", "to": "v", "kind": "realizes"}]]) is called
Then it returns {"width": 1100, "height": 100,
  "nodes": [{"id": "v", "x": 640, "y": 30, "labelX": 652, "labelY": 34}],
  "edges": [{"index": 0, "from": "v", "to": "v", "x1": 640, "y1": 30,
             "x2": 640, "y2": 30, "class": "edge-realizes"}]}
```
