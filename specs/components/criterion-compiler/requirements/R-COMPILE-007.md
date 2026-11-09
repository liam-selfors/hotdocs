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
  (`foo + 1`), field or index access (`foo.id`), concatenation, or a
  call — is expression evaluation and MUST be a specific, located compile
  error, never a best-effort evaluation. An author needing a bound value's
  field binds that value in its own `Given` step; allowing field access
  would mean extending the step-phrase grammar.
