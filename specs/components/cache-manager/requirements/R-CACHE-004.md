# R-CACHE-004

**R-CACHE-004** — On any backing-store error (unreachable
  `VAR-CACHE-STORE-URL`, timeout, corrupt stored entry), `get` MUST return a
  miss, never raise an exception or crash the caller: a broken cache degrades to "nothing is cached yet," not
  to a pipeline outage.
