- **Standard library only.** The module imports nothing outside
  Python's standard library, never `hotdocs` code.
- **No subprocess, no network.** The asset is parsed in the calling
  process; nothing is executed.
