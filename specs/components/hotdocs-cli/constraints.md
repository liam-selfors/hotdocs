# Hotdocs CLI — Non-Functional Constraints

- **Fresh loads.** Two projects in one process never share a loaded
  component module.
- **No hidden cost.** A model is injected only for verbs that cannot run
  without one; a read-only verb never gains one.
