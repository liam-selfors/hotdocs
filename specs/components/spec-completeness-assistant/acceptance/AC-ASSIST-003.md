# AC-ASSIST-003

Covers: R-ASSIST-003
Kind: generated-test

```gherkin
Given a repo_root with stand-ins for all four dependencies that record
  every call to a log file the test controls: lint returning no
  findings, a blast radius of comp-foo then comp-bar, and a check that
  returns an object whose to_dict() is {"findings": [], "target": <the
  first target>} for comp-foo and raises RuntimeError("boom") for comp-bar
When assist(["R-FOO-001"], repo_root, model="fake-model") runs
Then criterion_reviews is {"comp-foo": {"findings": [], "target":
  "comp-foo"}, "comp-bar": {"error": "boom"}}, and the log shows check
  called with ["comp-foo"] then ["comp-bar"], each with no model

Given the same setup
When assist(["R-FOO-001"], repo_root) runs with no model
Then criterion_reviews has the same two keys and the log shows no
  complete call
```
