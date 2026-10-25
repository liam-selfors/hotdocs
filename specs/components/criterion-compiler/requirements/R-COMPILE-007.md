# R-COMPILE-007

**R-COMPILE-007** — A step's literal value arguments MUST be parsed as
  literal data (strings, numbers, JSON), never evaluated as code — the
  compiler MUST NOT become an arbitrary-code-execution vector via crafted
  Gherkin.

  **Exact boundary for cross-step fixture references (resolves the open
  question this requirement previously left open):** a bare identifier
  occupying an entire leaf/scalar position within the literal syntax —
  whether as a whole argument value or nested inside a larger object/array
  literal (e.g. `{"owner": user_id}`) — MUST be treated as literal
  substitution, not evaluation, when it exactly matches a fixture name
  bound by an earlier `Given` step in the same criterion. The compiler
  resolves it at **compile time** to that fixture's own already-known
  literal value, by simple lookup — never by runtime computation, which is
  the actual property that keeps this safe under R-COMPILE-007's intent.
  A bare identifier that does not match any fixture bound earlier in the
  same criterion MUST be a compile error (the same unresolved-reference
  discipline `R-COMPILE-001`/`002` already apply to unmatched steps and
  undeclared interface members, extended here to cover this position
  too) — never a silent fallback to treating it as a literal string.

  Anything beyond a bare identifier in a leaf position — an operator
  (`foo + 1`), field or index access (`foo.id`), string concatenation, or
  a function-like call — crosses into expression evaluation and MUST be a
  specific, located compile error, never a silent best-effort evaluation
  attempt. This is a deliberate scope limit, not an oversight: field/index
  access into an already-bound literal *would* still be compile-time-only
  and therefore no less safe, but allowing it would mean extending the
  step-phrase grammar itself (`specs/architecture/step-phrase-grammar.md`,
  D2-level governance weight) for a need nothing in this corpus has
  actually raised yet. An author needing a bound value's field elsewhere
  MUST bind that field's value directly in its own `Given` step instead.
