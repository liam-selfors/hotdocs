# Verification

One directory per component, plus `corpus-graph.json`, the manifest that
`hotdocs track ui build` and `hotdocs docs-site build` render from
(`hotdocs corpus-graph build` writes it).

Each `verification/<slug>/` holds:

- `generated-test/` — one test file per acceptance criterion, written by
  `test-author` when the component was generated;
- `.provenance.json` — the manifest `hotdocs generate` writes: spec hash,
  model, verification report, mutation score;
- `BOOTSTRAP.md` — the account of how the component first landed: what was
  ambiguous, what was decided, which spec gaps each failed round exposed;
- for the hand-written components, a hand-written test suite instead of
  `generated-test/`.

Run a suite with the checkout's `.venv` active (the one environment, `D203`;
`pytest` is in `requirements.txt`), one directory per invocation, with the
component's `gen/` directory on `PYTHONPATH`:

```
cd verification/<slug> && PYTHONPATH=../../gen/<slug> pytest
```

Never run two directories in one `pytest` command: each has a bare-named
`conftest.py`, and Python's module cache makes any two collide. This is a
known quirk of non-package test directories, not a bug in any one suite.

`hotdocs verify` runs the same tests, plus mutation testing, interface drift
and the compliance scans, and reports one ready/not-ready verdict.
