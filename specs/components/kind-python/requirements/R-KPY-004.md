# R-KPY-004

**R-KPY-004** — `provision(repo_root)` MUST return a `ProvisionResult`
and never raise. When `<repo_root>/environments/python/requirements.lock`
is not a file, it writes nothing and returns `ok` true, `reason` `""`,
`lockfile_sha256` `None`, `interpreter` `sys.executable`, and
`versions` `{"python": <v>}`, `<v>` the stripped stdout of running
`sys.executable -c "import sys; print('%d.%d' % sys.version_info[:2])"`
(30-second timeout): major and minor only, so a patch release changes
no provenance key. With a lock it does what `R-KPY-005` states.

In either case, when that version command exits non-zero or times out,
the result is `ok` false with `reason`
`python environment: python version check failed`, `versions` `{}` and
`interpreter` `None`.
