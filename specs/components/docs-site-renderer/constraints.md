---
id: comp-docs-site-renderer-constraints
title: Docs Site Renderer — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Docs Site Renderer — Non-Functional Constraints

- **Purity.** A function of `corpus-graph.json` alone — no network access,
  no model calls, no other file reads.
- **Not committed.** Its output is a CI build artifact, deployed to a docs
  host — never checked into the repository (D9).
- **Cheap enough to run on every merge.** A render over already-computed
  data; MUST NOT become a merge-latency bottleneck the way a model-calling
  gate would.
