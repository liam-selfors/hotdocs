# R-SURF-001

**R-SURF-001** — After the environment check (`R-SURF-006`) found
  nothing, `check_surface` MUST run `import <module>` in a subprocess of
  the interpreter `R-SURF-006` gives, with `PYTHONPATH` `code_dir`. A non-zero exit gives one
  `import_error` finding whose message is the last non-empty line of its
  stderr, and no other check runs.
