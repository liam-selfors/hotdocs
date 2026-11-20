# Library

One module file, `spec_reviewer.py`, never a package.

```
check(targets: list[str], repo_root: Path, model: str | None = None, *,
      llm_backend=None, write_proposals: bool = False) -> ReviewReport
glossary_judge(model: str, llm_backend=None) -> callable
main(argv: list[str] | None = None) -> int
```

`targets` holds component ids (`comp-foo`, meaning every criterion under
`specs/components/foo/acceptance/`) and criterion ids (`AC-FOO-002`). An
id that names neither raises `ValueError`.

Each dependency is loaded from `<repo_root>/gen/<slug>/<module>.py`, or
from the same path under the tool root, the parent of the nearest
directory named `gen` above this module's file, when `repo_root` has no
such directory. They are called as:

1. `spec-linter`'s `lint(paths, repo_root, judge=...)`, with `paths` the
   named components' directories and `judge` the callable
   `glossary_judge(model, llm_backend)` returns, or `None` without a model;
2. `spec-bundle-assembler`'s `assemble_criterion(component_id,
   criterion_id, repo_root)`, once per criterion;
3. with a model only, `llm-endpoint`'s `complete(prompt, model,
   backend=llm_backend)`, once per criterion, and once per Definitions
   entry the judge is asked about.

`glossary_judge` returns a callable
`judge(term, local_text, glossary_text)` that makes one `complete` call
and returns `(conflicts, rationale)` from a reply holding the JSON object
`{"conflicts": <bool>, "rationale": "<text>"}`, or `None` for any other
reply or a `model_call_error`: `spec-linter`'s judge shape.

Test fixtures: a synthetic corpus that lints clean (`testing.md`). A mock model is
an `llm_backend(prompt, model, **params)` callable returning
`{"text": ..., "model": ..., "backend": "mock", "model_call_error": None}`.

Implements: `specs/architecture/criterion-visibility.md`, `specs/architecture/cli-conventions.md`
