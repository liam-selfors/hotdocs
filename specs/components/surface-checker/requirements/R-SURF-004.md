# R-SURF-004

**R-SURF-004** — `check_surface` MUST return its findings in check order,
  `R-SURF-006`, `R-SURF-001` to `R-SURF-003` then `R-SURF-005`; within the
  dependency check by dependency in `depends_on` order, then by name;
  within the asset check by asset in declaration order, then by name; `ok` is `true` exactly
  when there are none.
