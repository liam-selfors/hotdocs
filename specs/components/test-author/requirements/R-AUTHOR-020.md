# R-AUTHOR-020

**R-AUTHOR-020** — `author_test` MUST statically validate a response
  before accepting it, never relying on model self-check alone
  (`R-AUTHOR-015` is necessary but not sufficient).

  **Syntax check:** `ast.parse()` the extracted content first. A
  `SyntaxError` MUST be a distinct authoring failure (new
  `model_call_error` category `malformed_code`) — nothing written to
  cache or disk, same posture as `R-AUTHOR-009`'s missing marker pair.

  **Fake-arity check, best-effort:** for each `dep_id` in
  `dependency_interfaces`, parse every `name(args) -> ReturnType`
  signature from its text. Walk the test's top-level `FunctionDef`s,
  simple `name = other_name` aliases **resolved to their target
  function's own arity, never skipped as unresolvable** (`D126`),
  and any string literal that itself parses as valid Python (`D113`);
  for any name matching a real dependency function, compare parameter
  counts (`*args`/`**kwargs` satisfy any). A mismatch MUST be a
  distinct failure (`fake_signature_mismatch`, naming the function
  and both arities). Skip what can't be parsed unambiguously.

  Found at `D110`, `D113` (string-literal case), `D126` (unresolved
  alias case).