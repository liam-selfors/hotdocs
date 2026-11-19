# R-KPY-005

**R-KPY-005** — With a lock, `provision` MUST, in order, stopping at
the first failure:

1. **Pin check.** Read the lock as UTF-8. It pins `pytest` when some
   line, stripped, is non-empty, does not start with `#` or `-`, and
   whose text before the first of `=`, `<`, `>`, `!`, `~`, `[`, `;`,
   `@` or a space (all of it when none occurs), lowercased with every
   run of `-`, `_` and `.` replaced by one `-`, is exactly `pytest`.
   Otherwise: `reason` `python environment: requirements.lock does not pin pytest`,
   before anything is created.
2. **Serialize.** With `root = repo_root.absolute()`, create
   `root / ".hotdocs" / "env"` (parents included) and hold
   `fcntl.flock(LOCK_EX)` on `root / ".hotdocs" / "env" / "python.lock"`,
   opened for append, until `provision` returns. POSIX only: where
   `fcntl` cannot be imported, no lock is taken. An `OSError` here gives
   `python environment: <str(error)>`.
3. **Environment.** `env` is `root / ".hotdocs" / "env" / "python"`,
   `interpreter` is `str(env / "bin" / "python")`
   (`env / "Scripts" / "python.exe"` on Windows), never resolved, and
   the marker text is `<lockfile_sha256> <M>.<m>`, `<M>.<m>` the
   running `sys.version_info` major and minor. When `interpreter` is
   not an executable file (`os.access(..., os.X_OK)`), or
   `env / ".lock-sha256"` does not hold exactly the marker text, run
   `[sys.executable, "-m", "venv", "--clear", str(env)]`, then
   `[interpreter, "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "-r", str(lock)]`,
   then write the marker text, with no newline, to `env / ".lock-sha256"`.
   Otherwise nothing runs.
4. **Version**, as `R-KPY-004` states, with this `interpreter`.

Both commands get `os.environ` unchanged and are killed after 900
seconds. A non-zero exit gives `python environment: <line>`, `<line>`
the last non-empty stderr line, stripped, or `<program> exited <code>`
(`venv` or `pip`) when stderr has none; a timeout,
`python environment: <program> timed out`. A failure writes no marker.
Every failure is `ok` false with `versions` `{}`, `interpreter` `None`,
and `lockfile_sha256` the lock's.
