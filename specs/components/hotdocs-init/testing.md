# Testing hotdocs-init

All `kind: generated-test`: a temporary project directory
and a fake tool root.

A **fake tool root** holds `gen/<slug>/<module>.py` fakes for a few slugs,
among them `llm-endpoint` (fakes of the five names above that also log each
call to a file outside both the project and the tool root, so a log never counts as a change to either),
`examples/slugify/specs/product/slugs.md`, and a `requirements.txt` whose only line is
`pytest==` plus `importlib.metadata.version("pytest")` (so nothing is missing). A test embeds no secret-shaped string.
A criterion's `init runs` or `run([...])` calls `run` with a fake tool root as `tool_root`.
