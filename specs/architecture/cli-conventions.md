---
id: arch-cli-conventions
title: Conventions Every Component CLI Follows
status: draft
owners: [pipeline-team]
depends_on: []
---

# Conventions every component CLI follows

## Purpose

A component that implements this document gives `hotdocs` users one
predictable command-line behavior, and gives its tests and the surface
checker one contract to probe (`D299`).

## The `main` contract

- The component exposes `main(argv: list[str] | None = None) -> int`,
  importable from its module itself: a package re-exports it from its
  `__init__.py`.
  `argv` holds the tokens after the verb words `hotdocs-cli`'s verb table
  strips for that component; `None` means `sys.argv[1:]`.
- `main` returns an `int` exit code. It never calls `sys.exit` and never
  lets an exception escape for a usage error.
- Exit `0` means the command did its job; `1` means it ran and reports a
  failure the command itself defines; `2` means a usage error.

## Usage errors

Each of these is a usage error: `main` prints exactly one line,
`usage error: <cause>`, to stderr, prints the command's usage line to
stderr, writes nothing else, and returns `2`.

- an argument the command does not define, such as `--hotdocs-smoke-unknown`;
- a flag that takes a value given as the last token, with no value;
- a value outside the flag's documented set, such as `--format=bogus`;
- a required argument that is missing.

A flag that takes a value accepts both `--flag=value` and `--flag value`.

## Output

- Results go to stdout; usage errors and progress notices go to stderr.
- `--format=json`, where a command offers it, prints one JSON document
  and nothing else to stdout.
- No traceback is ever printed for a usage error.
