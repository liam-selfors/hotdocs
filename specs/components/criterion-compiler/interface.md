---
id: comp-criterion-compiler-interface
title: Criterion Compiler — Interface
status: draft
owners: [pipeline-team]
---

# Criterion Compiler — Interface

## CLI

```
hotdocs compile-criteria <acceptance.md> --interface=<interface.md> \
  [--target=pytest] [--out=<dir>] [--repo-root=<dir>]
```

- `<acceptance.md>` — the component's acceptance-criteria file to compile.
- `--interface` — the component's `interface.md`, for resolving step
  references. Required.
- `--target` — emitted test-framework target. Default and only supported
  value for v1: `pytest` (Python). Multi-target emission is an open question
  (`spec.md`).
- `--out` — output directory for compiled test files. Default:
  `verification/<component>/compiled/`.
- `--repo-root` — repository root. Defaults to the current git repository
  root.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Every `kind: compiled` criterion compiled successfully. |
| `1` | ≥1 criterion failed to compile (unrecognized step, unresolved reference, literal-safety violation). |
| `2` | Usage error. |

## Library

```
compile(acceptance_md: Path, interface_md: Path, target: str = "pytest") -> CompileReport
```

A pure function over its two file inputs — no network access, no model
calls, no side effects beyond writing the files it's asked to write.

## The step grammar

Steps are **not open natural language** — this is what keeps compilation
model-free and deterministic. Each step matches exactly one of a small, fixed
set of templates, each binding to one of three roles (setup / exercise /
assert):

| Role | Template | Compiles to |
| --- | --- | --- |
| setup (`Given`) | `a <fixture-name> is <literal>` | a bound local variable `<fixture-name> = <literal>` |
| setup (`Given`) | `a <Type> with <field>: <literal>[, <field>: <literal>]*` | construction of `<Type>` (resolved against `interface.md`'s declared types) with the given literal fields |
| exercise (`When`) | `<function-or-endpoint> is invoked with <args>` | a call to the named function/endpoint (resolved against `interface.md`), capturing the result as `result` |
| exercise (`When`) | `the client calls <METHOD> <path> with <args>` | an HTTP-style invocation against the named endpoint (resolved against `interface.md`), capturing the result as `result` |
| assert (`Then`) | `<result-path> equals <literal>` | an equality assertion on `result.<result-path>` |
| assert (`Then`) | `the <artifact> contains a <severity>-severity finding for rule <rule-id>` | a structured-containment assertion against `result` (the pattern this project's own `spec-linter`/`criterion-compiler` acceptance criteria themselves use) |

Any step not matching one of these templates, or referencing a
function/endpoint/type/field not declared in `interface.md`, is a **compile
error** naming the file, line, and the specific unresolved reference or
unmatched text — never a silent skip or a best-effort guess (R-COMPILE-001/002).

Literal values are JSON-like scalars, strings, or object/array literals only
— never expressions. A fixture name referenced in a later step (e.g. a
`Given`-bound variable used in a `When` step's args) resolves to the literal
it was bound to; this is the one allowed form of cross-step reference, and it
is still a literal substitution, not evaluation (see `spec.md`'s open
question on this boundary).

## Data: `CompileReport`

```json
{
  "outputs": [
    {
      "criterion_id": "AC-LINT-003",
      "covers": "R-LINT-003",
      "status": "compiled",
      "file": "verification/spec-linter/compiled/test_ac_lint_003.py"
    },
    {
      "criterion_id": "AC-LINT-999",
      "covers": "R-LINT-999",
      "status": "error",
      "message": "step 'When a wizard appears' does not match any recognized template"
    }
  ],
  "gate_version": "criterion-compiler@1.0.0",
  "summary": {
    "compiled": 14,
    "errors": 0,
    "skipped_non_compiled_kind": 0
  }
}
```

`gate_version` corresponds to the `gate_versions.compiler` entry in the D7
provenance manifest (R-COMPILE-010).
