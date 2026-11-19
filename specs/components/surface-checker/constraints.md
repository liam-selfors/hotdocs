# Surface Checker — Non-Functional Constraints

- **No model calls and no network access.**
- **The candidate runs only in a subprocess**, never imported into the
  caller's process, each with a 60-second timeout, except the `python`
  adapter's `provision`, which may build an environment: 600 seconds.
- **Read-only.** Writes nothing under `repo_root`.
