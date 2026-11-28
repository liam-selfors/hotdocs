# R-RUNENV-005

**R-RUNENV-005** — `prepare` and `prepare_capability` MUST NOT raise for
  an adapter: one that fails to load, or whose `provision` raises, ends
  provisioning as an `ok` false report would, with `failure_message`
  `<kind or driver name> adapter failed: <ExceptionType>: <message>`,
  `<ExceptionType>` the exception's class `__name__` and `<message>` its
  `str()`. A missing `component.md`, or one with no `assets` or
  `drivers` line, declares none.
