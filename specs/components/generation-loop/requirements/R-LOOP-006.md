# R-LOOP-006

**R-LOOP-006** — `make_closures(model, seed, repo_root, llm_backend)` MUST
  return `(test_author, judge)`. `test_author(bundle)` calls
  `author_test(bundle, model, seed=seed, repo_root=repo_root,
  llm_backend=llm_backend)` and returns its result. `judge(bundle)` makes
  exactly one `complete` call whose prompt contains the bundle's
  `criterion_text`, `requirement_text` and `interface` and the full text
  of every file under `<repo_root>/gen/<slug>/` (skipping `__pycache__`),
  and asks for JSON `{"result": "pass" | "fail", "rationale": "..."}`; a
  reply wrapped in a Markdown code fence is unwrapped first, and it
  returns that `{result, rationale}`. A `model_call_error`, unparseable
  text, or a `result` other than `"pass"` or `"fail"` returns
  `{"result": "fail", "rationale": "judge unavailable: <reason>"}`,
  never a pass and never raised.
