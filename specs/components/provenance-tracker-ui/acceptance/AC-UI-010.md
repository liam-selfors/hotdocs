# AC-UI-010

Covers: R-UI-010
Kind: generated-test

```gherkin
Given run = asset_runner("static/app.js") and
  nodes = [{"id": "a", "status": "passing"},
           {"id": "b", "status": "failing"},
           {"id": "c", "status": "missing"},
           {"id": "d", "status": "not-attempted"},
           {"id": "e", "status": "passing"}]
When run("hiddenByStatus", [nodes, <filter>]) is called
Then it returns exactly
  | filter          | result                                                  |
  | "all"           | {"a": false, "b": false, "c": false, "d": false, "e": false} |
  | "passing"       | {"a": false, "b": true, "c": true, "d": true, "e": false}     |
  | "failing"       | {"a": true, "b": false, "c": true, "d": true, "e": true}      |
  | "missing"       | {"a": true, "b": true, "c": false, "d": true, "e": true}      |
  | "not-attempted" | {"a": true, "b": true, "c": true, "d": false, "e": true}      |
  | "Passing"       | {"a": true, "b": true, "c": true, "d": true, "e": true}       |
  | "bogus"         | {"a": true, "b": true, "c": true, "d": true, "e": true}       |

Given the same run
When run("hiddenByStatus", [[], "all"]) and
  run("hiddenByStatus", [[], "passing"]) are called
Then each returns {}

Given a rendered index.html for a snapshot with one node of each status
When its filter buttons are inspected
Then it contains exactly five button elements with data-filter
  attributes, in order "all", "passing", "failing", "missing",
  "not-attempted", and no node element carries a hidden attribute
```
