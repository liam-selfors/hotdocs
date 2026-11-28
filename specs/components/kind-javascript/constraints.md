# Kind javascript — Non-Functional Constraints

- **Standard library only.** The module imports nothing outside
  Python's standard library, never `hotdocs` code.
- **No long JavaScript in Python strings.** Each JavaScript text the
  module holds is one Python string constant under 200 characters
  (`R-KJS-005`), measured by `len` of the constant.
