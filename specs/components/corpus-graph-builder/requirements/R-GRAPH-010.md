# R-GRAPH-010

**R-GRAPH-010** — `build_corpus_graph` MUST load `graph-query-engine`'s
  `graph_query_engine.py` by file path from
  `<repo_root>/gen/graph-query-engine/`, or from the tool root's when
  that directory is absent (`D199`), never by a bare `import
  graph_query_engine`, which works only when a caller has already put
  that directory on `sys.path`.
