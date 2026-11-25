# R-LICENSE-012

**R-LICENSE-012** — `gen/<component>/`'s content (`R-LICENSE-001`) MUST
  be exactly the files under that directory, at any depth, except a file
  whose name starts with `.` (the component's `.provenance.json` and
  `.overrides.json`), a file ending `.pyc`, and every file under a
  directory named `__pycache__` or whose name starts with `.`. The
  similarity score and the cache key's `gate_inputs_hash`
  (`R-LICENSE-004`) MUST both read exactly these files, so writing a
  manifest or importing the code never changes a later scan's score
  (`D372`).
