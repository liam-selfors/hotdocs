# Library

One module file, `generation_loop.py`, never a package.

```
run_attempts(component_id: str, bundle, repo_root: Path, model: str, *,
             mode: str = "single", max_attempts: int = 3,
             retry_feedback: list[str] | None = None, seed: int = 0,
             llm_backend=None, allow_unisolated_exec: bool = False,
             on_attempt=None) -> AttemptLoopResult
make_closures(model: str, seed: int, repo_root: Path, llm_backend=None) -> tuple
RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")
```

`mode` is `"single"` or `"agentic"`; any other value, or a
`max_attempts` below `1`, raises `ValueError` before any call.
`on_attempt(attempt: dict, generation_result, verification_report)` is
called after every attempt with that attempt's `AttemptLoopResult.attempts`
entry; `verification_report` is `None` when no verification ran.

Each dependency is loaded from `<repo_root>/gen/<slug>/<module>.py`,
else from the tool root's copy, and called as:

- `generator`'s `generate(bundle, model, feedback, repo_root=repo_root,
  llm_backend=llm_backend)` in single mode, and its
  `commit_cache(result, repo_root=repo_root)` after a single-mode pass;
- `agentic-generator`'s `generate_agentic(bundle, model, feedback,
  repo_root=repo_root, allow_unisolated_exec=allow_unisolated_exec)` in
  agentic mode;
- `surface-checker`'s `check_surface(component_id, repo_root)`;
- `verifier-orchestrator`'s `verify(component_id, repo_root, judge=judge,
  test_author=test_author)`, with the closures `make_closures` builds;
- `test-author`'s `author_test(criterion_bundle, model, seed=seed,
  repo_root=repo_root, llm_backend=llm_backend)` inside the
  `test_author` closure, and `llm-endpoint`'s `complete(prompt, model,
  backend=llm_backend)` inside the `judge` closure.

`feedback` is `None` when the list is empty, and is always the third
positional argument, never a keyword. `on_attempt` is called
positionally. `make_closures` returns the tuple `(test_author, judge)`,
in that order.

## How it works

Each dependency module is loaded on first use, at most once per
`run_attempts` call, and reused for every attempt, so a stand-in may keep
state in module globals. It is loaded under a name unique to that load,
never taken from or left in `sys.modules`. The closures load
`test-author` and `llm-endpoint` only when called. `run_attempts` reads
nothing else from `repo_root` and writes nothing under it.

`bundle` is passed unchanged to `generate`/`generate_agentic`; the loop
never reads it, so a test may pass any mapping. `judge` reads its bundle
by key, taking `<slug>` from `component_id` with `comp-` stripped.

Results may be dicts or objects, read with dual dict-or-attribute access;
an absent field reads as `None` (`files` and `criteria` as empty). The
loop reads only: from a generation result `files`, `refused`,
`transcript_sha256` and `model_call_error`, which is
`{"category": ..., "message": ...}`, its `category` becoming
`error_category`; from a surface report `ok`; from a verification report
`overall` and each criterion's `covers`, `result` and `failure_origin`.
Results reach `on_attempt`, `commit_cache` and `AttemptLoopResult` as the
very objects the dependencies returned, never copies.

An attempt whose generation made no files runs neither `check_surface`
nor `verify`. After a `surface_failed` or `verification_failed` attempt
another follows while fewer than `max_attempts` have run, even when it
added no feedback ids, unless the loop stops with `environment`
(R-LOOP-004); `not_retried` applies only to a `generation_failed`
attempt.

Implements: `specs/architecture/test-reuse.md`
