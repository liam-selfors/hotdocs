# R-LOOP-005

**R-LOOP-005** — After every attempt, `on_attempt`, when given, MUST be
  called once with that attempt's entry, its generation result and its
  verification report or `None`. `attempts` lists every attempt in order,
  numbered from `1`, each `transcript_sha256` copied from its generation
  result; `generation_result`, `verification_report` and
  `surface_report` are the last attempt's, `None` where it made none,
  each the very object the dependency returned. An attempt whose
  generation made no files has `surface_ok` and `overall` `None` and
  `failed_requirements` `[]`, and `on_attempt` receives `None` as its
  report.
