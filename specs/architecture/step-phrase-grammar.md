---
id: arch-step-phrase-grammar
title: Step-Phrase Grammar
status: draft
owners: [pipeline-team]
depends_on: []
---

# Step-Phrase Grammar

## Purpose

The fixed Given/When/Then step grammar every `compiled`-kind acceptance
criterion in the corpus is written against, and that `criterion-compiler`
implements. Lives here, not inside `criterion-compiler/interface/`, because
changing it is a corpus-wide, architecture-level decision (the same
governance weight as splitting a component) — it's a breaking change to
every `compiled` criterion in the corpus, not a routine edit to one
component's own contract. Moved here from `criterion-compiler/interface/`
during the D1 one-file-per-unit migration, which made the mismatch between "where
this content lived" and "what governance it actually needs" visible for
the first time — a flat `interface.md` didn't force the question the way
an explicit `interface/` directory, scoped to one component's own contract,
did.

## The grammar

Steps are **not open natural language** — this is what keeps compilation
model-free and deterministic. Each step matches exactly one of a small, fixed
set of templates, each binding to one of three roles (setup / exercise /
assert):

| Role | Template | Compiles to |
| --- | --- | --- |
| setup (`Given`) | `a <fixture-name> is <literal>` | a bound local variable `<fixture-name> = <literal>` |
| setup (`Given`) | `a <Type> with <field>: <literal>[, <field>: <literal>]*` | construction of `<Type>` (resolved against the target component's `interface/` contract) with the given literal fields |
| exercise (`When`) | `<function-or-endpoint> is invoked with <args>` | a call to the named function/endpoint (resolved against the target component's `interface/`), capturing the result as `result` |
| exercise (`When`) | `the client calls <METHOD> <path> with <args>` | an HTTP-style invocation against the named endpoint (resolved against the target component's `interface/`), capturing the result as `result` |
| assert (`Then`) | `<result-path> equals <literal>` | an equality assertion on `result.<result-path>` |
| assert (`Then`) | `the <artifact> contains a <severity>-severity finding for rule <rule-id>` | a structured-containment assertion against `result` (the pattern this project's own `spec-linter`/`criterion-compiler` acceptance criteria themselves use) |

Any step not matching one of these templates, or referencing a
function/endpoint/type/field not declared in the target component's
`interface/`, is a **compile error** naming the file, line, and the specific
unresolved reference or unmatched text — never a silent skip or a
best-effort guess (`criterion-compiler`'s `R-COMPILE-001`/`002`).

**Exact forms** (`D214`). `<fixture-name>` is an identifier
(`[A-Za-z_][A-Za-z0-9_]*`); `<Type>` is one starting with a capital.
`<function-or-endpoint>` is an identifier that may contain dots. A
`<literal>` is a JSON value (string, number, `true`/`false`/`null`,
object, array) in which a bare fixture name may stand for any scalar
value. `<args>` is one such literal: an object becomes keyword arguments
(`with {"text": payload}` compiles to `f(text=<payload's literal>)`), an
array becomes positional arguments, and any other value a single
positional argument. A `<result-path>` is an identifier with optional
`.field` and `[index]` parts, asserted as `result.<result-path>`.

Literal values are JSON-like scalars, strings, or object/array literals only
— never expressions. A fixture name referenced in a later step (e.g. a
`Given`-bound variable used in a `When` step's args) resolves to the literal
it was bound to — a bare identifier in a leaf/scalar position only, resolved
at compile time by simple lookup; this is the one allowed form of cross-step
reference, and it is still a literal substitution, not evaluation. Anything
beyond a bare identifier (an operator, field/index access, concatenation, a
call) is expression evaluation and a compile error — see `criterion-compiler`'s
`R-COMPILE-007` for the full rule and rationale.

## Change log

- Initial draft, relocated here from `criterion-compiler/interface/` during
  the D1 migration.
