# Kind python — Non-Functional Constraints

- **No model calls.** The module makes no network access itself; only
  the `pip` it runs for a project's lock may, as the lock directs.
- **Standard library only.** The module imports nothing outside
  Python's standard library, never `hotdocs` code.
- **Writes only where stated.** It writes nothing but the environment
  directory and its marker (`R-KPY-005`) and the file `apply_site`
  rewrites; it never writes into a code directory otherwise.
- **Bounded.** Every subprocess but `venv` and `pip` is killed after 30
  seconds; those two after 900 seconds.
