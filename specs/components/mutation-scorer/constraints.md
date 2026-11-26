# Mutation Scorer — Non-Functional Constraints

- **Writes only in its sandbox.** `<repo_root>` is never modified.
- **Never raises for a run**: every failure is a `mutation_error`
  (`R-MUT-005`).
