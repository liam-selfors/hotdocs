# Hotdocs Init — Non-Functional Constraints

- **Never installs, never reads a secret.** Missing prerequisites are
  reported with the command to run. An API key is never asked for, stored,
  or printed; only the NAME of its environment variable is.
- **Never overwrites.** Anything that exists is skipped, and reported.
- **Fail before writing.** A name collision or an unusable target stops
  `init` before anything is written.
