---
id: arch-agent-sandbox
title: Agent Sandbox
status: draft
owners: [pipeline-team]
depends_on: []
---

# Agent Sandbox

## Purpose

The exact rules for the directory an agentic generation works in, the
tools it gets, and how code the model writes is run, so that the model
sees only its spec bundle and nothing it runs can reach the network,
the repository, or a credential.

## Layout

One directory made by `tempfile.mkdtemp(prefix="hotdocs-agent-")`, its
real path `<root>`, holding exactly:

- `bundle/`: one file per `(title, text)` pair of `generator`'s
  `render_prompt_sections(bundle, retry_feedback)`, named
  `<NN>-<slug>.md` (`NN` the 1-based position, two digits; `slug` the
  title lowercased, each run of characters other than `a-z0-9` replaced by
  one `-`, leading and trailing `-` removed), holding the text. Every file
  is mode `0o444` and the directory `0o555`.
- `work/`: empty; the candidate, laid out as `generator`'s `R-GEN-015`
  says (`<module>.py` or `<module>/__init__.py` and other files).
- `scratch/`: empty; the model's own tests. Never kept.
- `tmp/`: the run's `TMPDIR` and `HOME`.

Nothing else from the repository is ever copied in.

## Paths

A tool's `path` argument is relative to `<root>`, written with `/`. It
is rejected, with the error result `path not allowed: <path>`, when it
is empty or absolute, has a `..` part, has a first part that is not
`bundle`, `work` or `scratch` (only `work` and `scratch` for a write or
delete), passes through a symbolic link at any level, or resolves by
`os.path.realpath` outside `<root>`.

## Tools

The tools are given to the model in this table's order. Each tool's
result is text, cut to its first 8192 characters followed by
`\n[truncated]` when longer.

| Tool | Arguments | Result |
| --- | --- | --- |
| `list_files` | `path` (a directory) | every file at any depth under `path`, one per line as its path relative to `<root>` written with `/` (e.g. `bundle/01-spec.md`, so it can be passed straight to `read_file`), sorted by string order, joined with `\n`, no trailing newline; `""` when there are none |
| `read_file` | `path` | the file's bytes decoded as UTF-8, undecodable bytes replaced |
| `write_file` | `path`, `content` | `wrote <path>`; writes `content` exactly as given, UTF-8 encoded; makes parent directories |
| `delete_file` | `path` | `deleted <path>` |
| `check_import` | none | `<exit code>\n<output>` of `import <module>` |
| `run_scratch_tests` | none | `<exit code>\n<output>` of pytest over `scratch/` |
| `finish` | `summary` | `finished`; every later call is answered `already finished` as an error |

A call is checked in this order, the first failing check giving its
error result: after a successful `finish`, `already finished`, whatever
the call's name or arguments; an unknown tool name, `bad call: unknown
tool <name>`; an argument whose key is absent or whose value is not a
string, `bad call: missing <argument>`; the `path` rules (Paths), so a
present but empty `path` is `path not allowed: `; then the limits.

`write_file` rejects content over 524288 bytes UTF-8 encoded with
`too large: <path> is <n> bytes, limit 524288`, and a new file that
would make `work/` and `scratch/` together hold more than 200 files
with `too many files: limit 200`.

A path that passes the rules but names nothing, or names a directory
for `read_file` or `delete_file`, or a file for `list_files`, is the
error result `not found: <path>`. Any other `OSError` while running a
tool is the error result `<tool> failed: <message>`.

## Running code

`check_import` runs `<python> -c "import <module>"` and
`run_scratch_tests` runs
`<python> -m pytest -q -p no:cacheprovider --noconftest scratch`, each
with current directory `<root>`, `<python>` being the `interpreter`
that the `python` adapter's `provision(repo_root)` reports
(`asset-kinds.md`'s Lookup; the project's own environment when it
commits `environments/python/requirements.lock`, else `sys.executable`,
`D355`), provisioned once per `generate_agentic` call (a failing `provision`
has already ended generation, as `asset-kinds.md`'s Layout step says).
The environment is exactly: `PATH=/usr/bin:/bin`, `HOME` and `TMPDIR`
`<root>/tmp`, `PYTHONPATH` `<root>/work`, `PYTHONDONTWRITEBYTECODE=1`,
and nothing else. Before exec the child sets `RLIMIT_CPU` to 60 seconds
and `RLIMIT_NOFILE` to 256, and the run is killed after 60 seconds of
wall time, its result then `timeout\n<output so far>`.

The command runs inside an OS sandbox that denies network access, writes
outside `<root>`, and reads of the repository's content:

- **macOS:** `/usr/bin/sandbox-exec -f <root>.sb -D ROOT=<root>
  -D REPO=<repo_root real path> -D PREFIX=<prefix> <command>`
  with the profile, `<prefix>` being the real path of `<python>`'s own
  `sys.prefix`, printed by `<python> -I -c "import sys; print(sys.prefix)"`
  (inside the repository when the environment is the project's)

  ```
  (version 1)
  (allow default)
  (deny network*)
  (deny file-write*)
  (allow file-write* (subpath (param "ROOT")) (literal "/dev/null"))
  (deny file-read-data (subpath (param "REPO")))
  (allow file-read-data (subpath (param "PREFIX")) (subpath (param "ROOT")))
  ```

  written to the file `<root>.sb`, beside `<root>` and outside it, so the
  model cannot change it; it is removed with `<root>`.
- **Linux:** `bwrap --ro-bind / / --tmpfs <repo_root> --ro-bind <prefix>
  <prefix> --bind <root> <root> --dev /dev --proc /proc --unshare-net
  --die-with-parent --chdir <root> -- <command>`.

**Isolation** is `sandbox-exec` or `bwrap` when used. With neither
available (not that platform, or the executable not found), the two
tools are answered `no OS sandbox available: code is not run` as an
error and isolation is `none`, unless the caller passed
`allow_unisolated_exec=True`, which runs the command without one and
records isolation `unisolated`.
