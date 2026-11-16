# R-PROBE-002

**R-PROBE-002** — `probe` MUST check the source with pyflakes
  (`pyflakes.api.check(test_source, "test_probe_target.py", reporter)`)
  and report one `undefined_name` finding, with its line, for each
  message pyflakes reports as an undefined name, its `message` being
  `undefined name '<name>'`. Every other pyflakes message is ignored.
