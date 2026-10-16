# R-CACHE-004

**R-CACHE-004** — On any backing-store error (unreachable
  `VAR-CACHE-STORE-URL`, timeout, corrupt stored entry), `get` MUST return a
  miss, never raise an exception or crash the caller — the same "the tool
  must keep working" posture D10 established for model availability, applied
  here to the cache: a broken cache degrades to "nothing is cached yet," not
  to a pipeline outage.
