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
2. **Environment.** `env` is `repo_root.absolute() / ".hotdocs" / "env" / "python"`
   and `interpreter` is `str(env / "bin" / "python")`
   (`env / "Scripts" / "python.exe"` on Windows), never resolved. When
   that file does not exist, run `[sys.executable, "-m", "venv", str(env)]`.
3. **Install.** When `env / ".lock-sha256"` does not hold exactly the
   lock's `lockfile_sha256` text, run
   `[interpreter, "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "-r", str(lock)]`;
   on success write that text, with no newline, to `env / ".lock-sha256"`.
   A matching marker runs nothing.
4. **Version**, as `R-KPY-004` states, with this `interpreter`.

Both commands get `os.environ` unchanged and are killed after 900
seconds. A non-zero exit gives `reason`
`python environment: <line>`, `<line>` the last non-empty line of its
stderr, stripped, or `<program> exited <code>` (`venv` or `pip`) when
stderr has none; a timeout gives `python environment: <program> timed out`.
A failed install writes no marker. Every failure is `ok` false with
`versions` `{}`, `interpreter` `None`, and `lockfile_sha256` the lock's.
