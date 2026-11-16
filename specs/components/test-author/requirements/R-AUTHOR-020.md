# R-AUTHOR-020

**R-AUTHOR-020** — `author_test` MUST statically validate a response
  before accepting it, never relying on model self-check alone.

  **Syntax check:** `ast.parse()` the extracted content first. A
  `SyntaxError` is a distinct failure (`model_call_error` category
  `malformed_code`); nothing is cached or written (`R-AUTHOR-009`).

  **Fake-arity check, best-effort:** parse every `name(args) ->
  ReturnType` signature from each `dependency_interfaces` entry; a comma
  inside brackets never splits a parameter (`dict[str, str]` is one). Walk
  the test's top-level `FunctionDef`s, simple `name = other_name`
  aliases resolved to their target's arity (`D126`), and string
  literals that parse as Python (`D113`); for a name matching a
  dependency function, compare parameter counts (`*args`/`**kwargs`
  satisfy any). A name more than one dependency defines matches if it fits any of their
  arities (`D166`). A mismatch is a distinct failure
  (`fake_signature_mismatch`, naming the function and both arities).
  Skip what can't be parsed unambiguously (`D110`).
