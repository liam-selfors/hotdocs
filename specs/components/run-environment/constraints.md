# Run Environment — Non-Functional Constraints

- **Never raises for an environment.** Every adapter failure is
  reported in `RunEnvironment`, never thrown (`R-RUNENV-005`).
- **No network access** but what an adapter's `provision` does.
