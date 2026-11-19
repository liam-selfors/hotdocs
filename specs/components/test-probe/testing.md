# Testing test-probe

**The planted wrapper interpreter** lives in a fresh temporary directory
`<w>` (pytest's `tmp_path`): an empty file `<w>/site/wraponly_pkg.py`,
which nothing else can import, and an executable file `<w>/pywrap`
(mode `0o755`, POSIX shell) with exactly the lines

    #!/bin/sh
    PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}<w>/site" exec '<sys.executable>' "$@"

`<w>` and the test's own `sys.executable` written in. Its path,
`str(<w>/pywrap)`, is the `interpreter` the criterion passes.
