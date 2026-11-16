# R-SURF-001

**R-SURF-001** — `check_surface` MUST first run `import <module>` in a
  subprocess with `PYTHONPATH` `code_dir`. A non-zero exit gives one
  `import_error` finding whose message is the last non-empty line of its
  stderr, and no other check runs.
