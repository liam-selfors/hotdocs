---
id: arch-tool-version
title: The Tool Version
status: draft
owners: [pipeline-team]
depends_on: []
---

# The Tool Version

## Purpose

The version of hotdocs is set in one place, so the command, a project's
marker file and the published package can never disagree (`D360`).

## Rules

The tool version is the `version` value of the `[project]` table of
`<tool_root>/pyproject.toml`, a string such as `0.1.0` or `0.1.0a1`.

A component that reports it reads that file each time it needs the
value, as bytes parsed with `tomllib`, and holds no version literal of
its own. When the file is absent, cannot be read, is not valid TOML,
has no `[project]` table, or that table's `version` is not a non-empty
string, the tool version is the string `unknown`. Reading it never
raises and never writes.

An installed package's tool root holds a `pyproject.toml` with the
released version (`tools/build_dist.py`, `D358`); a checkout's tool
root is the repository, whose `pyproject.toml` is the one that is
edited.

A test gives a fake tool root a `pyproject.toml` holding

```
[project]
name = "hotdocs"
version = "9.8.7a1"
```

and expects `9.8.7a1`; with no such file, with the content `not toml [`,
or with a file holding only `[tool.x]`, it expects `unknown`.
