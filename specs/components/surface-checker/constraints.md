# Surface Checker — Non-Functional Constraints

- **No model calls and no network access.**
- **The candidate runs only in a subprocess**, never imported into the
  caller's process, each with a 60-second timeout.
- **Read-only.** Writes nothing under `repo_root`.
