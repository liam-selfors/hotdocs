# Docs Site Renderer — Non-Functional Constraints

- **Purity.** A function of `corpus-graph.json` alone — no network access,
  no model calls, no other file reads besides its own asset
  `static/app.js` (`R-DOCS-001`).
- **Not committed.** Its output is a CI build artifact, deployed to a docs
  host — never checked into the repository (`notes/initial-ideas.md`'s
  own D9).
- **Cheap enough to run on every merge.** A render over already-computed
  data; MUST NOT become a merge-latency bottleneck the way a model-calling
  gate would.
