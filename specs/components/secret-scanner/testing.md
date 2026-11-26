# Testing secret-scanner

Every criterion is `kind: generated-test` (`D43`).

`scan` covers every file under `repo_root`, a test's stand-ins
included, so a stand-in embeds no long random-looking literal, above all
no temporary-directory path; it reads such values from an environment
variable.
