# R-GRAPH-007

**R-GRAPH-007** — `corpus_graph_builder.cli.main(argv)` MUST implement
  `interface/cli.md` exactly: `build` with an optional `--repo-root`
  (`--repo-root=<dir>` or `--repo-root <dir>`, default the current
  directory) builds and writes the graph, prints the written path, and
  returns `0`; any exception while building returns `1`; anything else
  returns `2`, never raising. Rebuilding on every merge to `main` is
  the CI's job, not this component's (`D200`).
