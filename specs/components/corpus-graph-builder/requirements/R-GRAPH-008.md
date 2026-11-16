# R-GRAPH-008

**R-GRAPH-008** — The graph MUST be a deterministic function of corpus +
  provenance + verification state: the same inputs always produce the
  same `to_json_bytes()`, byte for byte, because this file is committed
  and must regenerate identically on a provenance hit like any other
  committed artifact. Every value in it is plain JSON; none is a type
  `json.dumps` cannot write, such as a timestamp DuckDB parsed out of a
  manifest (`D200`).
