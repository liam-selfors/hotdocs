# R-AUTHOR-020

**R-AUTHOR-020** — `author_test` MUST statically validate a response
  before accepting it, never relying on model self-check alone.

  **Syntax check:** `ast.parse()` the extracted content first. A
  `SyntaxError` is a distinct failure (`model_call_error` category
  `malformed_code`); nothing is cached or written (`R-AUTHOR-009`).

  **Fake-arity check, best-effort:** parse every `name(args) ->
  ReturnType` signature from each `dependency_interfaces` entry; a comma
  inside brackets never splits a parameter (`dict[str, str]` is one). A
  function is a fake, and checked, only when it stands in for a
  dependency function: one defined in a string literal of the test
  that parses as Python, a fake module's source (`D113`); or a
  top-level function, or a simple `name = other_name` alias of one
  (`D126`), installed under a dependency function's name by
  `monkeypatch.setattr(target, "<name>", fn)`,
  `setattr(target, "<name>", fn)` or `target.<name> = fn`, checked as
  `<name>`. A top-level helper installed nowhere is never a fake,
  whatever its name (`D334`). Compare each fake's parameter count with
  the dependency function's (`*args`/`**kwargs` satisfy any). A name more than one dependency defines matches if it fits any of their
  arities (`D166`). A mismatch is a distinct failure
  (`fake_signature_mismatch`, naming the function and both arities).
  Skip what can't be parsed unambiguously (`D110`).
