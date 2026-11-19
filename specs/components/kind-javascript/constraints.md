# Kind javascript — Non-Functional Constraints

- **No model calls and no network access** by the module itself; the
  asset's process is denied file access beyond its copy and driver.
- **Standard library only.** The module imports nothing outside
  Python's standard library, never `hotdocs` code.
- **Leaves nothing behind.** Every file it writes, except the
  `asset_file` that `apply_site` rewrites, is under a temporary
  directory it removes before returning or raising.
- **Bounded.** Every `node` process is killed after 30 seconds.
- **No long JavaScript in Python strings.** Each JavaScript text the
  module holds is one Python string constant under 200 characters
  (`R-KJS-005`), measured by `len` of the constant.
