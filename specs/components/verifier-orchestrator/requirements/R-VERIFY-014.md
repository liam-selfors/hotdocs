# R-VERIFY-014

**R-VERIFY-014** — Every test run MUST have a wall-clock timeout,
  killing the whole process tree: 300 seconds for a run on unmutated
  code, and for a mutant's run 2 seconds or 10× the unmutated suite's
  own run time, whichever is larger. A mutant whose run times out
  counts as killed; a timed-out run on unmutated code fails that
  criterion (`D158`, after a mutant made a loop infinite).

  A mutant's tests MUST run with both the working directory and
  `PYTHONPATH` set to the mutated copy, never `repo_root`, so a test's
  relative `sys.path` entry (e.g. `gen/foo`) cannot import the original
  module (`D159`), and with pytest's `--noconftest`, so a hand suite's
  `verification/<slug>/conftest.py` above the generated tests cannot
  import it either (`D280`).
