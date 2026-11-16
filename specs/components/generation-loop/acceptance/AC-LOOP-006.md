# AC-LOOP-006

Covers: R-LOOP-006
Kind: generated-test

```gherkin
Given a repo_root with gen/widget/widget.py containing "CODE-MARK = 1"
  and gen/widget/__pycache__/x.pyc, a test-author stand-in recording its
  arguments, and an llm-endpoint stand-in recording each prompt and
  replying "```json\n{\"result\": \"pass\", \"rationale\": \"ok\"}\n```"
When test_author, judge = make_closures("m", 4, repo_root) and both are
  called with a bundle {"component_id": "comp-widget", "criterion_text":
  "CRIT", "requirement_text": "REQ", "interface": "IFACE"}
Then author_test received that bundle, "m" and seed 4; judge returned
  {"result": "pass", "rationale": "ok"}; and the prompt contained "CRIT",
  "REQ", "IFACE" and "CODE-MARK = 1"

Given replies of {"result": "maybe", "rationale": "x"}, of "no json", and
  a model_call_error
When judge is called with each
Then each returns result "fail" with a rationale starting
  "judge unavailable: "
```
