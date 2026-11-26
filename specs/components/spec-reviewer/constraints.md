# Spec Reviewer — Non-Functional Constraints

- **Advisory only.** No gate reads its report, and it never changes a
  file under `specs/`. The only files it writes are proposals under
  `<repo_root>/.hotdocs/proposals/`, and only when asked.
- **The model sees exactly one criterion's bundle per call.** Never two
  criteria, never the code, never `constraints.md`: the call stands in
  for that criterion's test author.
- **No network access** other than through `llm-endpoint`.
