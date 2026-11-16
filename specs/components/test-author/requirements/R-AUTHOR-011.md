# R-AUTHOR-011

**R-AUTHOR-011** — The prompt MUST include each entry of
  `dependency_interfaces`, one per
  dependency, and MUST instruct the model that any fake it writes for a
  dependency's behavior MUST match that dependency's real, documented
  call signature and return shape exactly, never invented or simplified.

  Prose alone proved insufficient for return shape (`D113`): the prompt
  MUST also include one worked example — given a documented return type
  with named fields, the fake MUST expose every field, never a bare
  list/string/number even if the test reads only one.
