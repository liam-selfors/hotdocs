# R-PROVCHECK-007

**R-PROVCHECK-007** — `current_sealed_key(component_id, repo_root)` MUST
  return `None` unless `<repo_root>/specs/components/<slug>/component.md`
  exists and its frontmatter has the line `sealed: true`. Otherwise it
  MUST return a `SealedKey` (`interface/data/SealedKey.md`):

  - `owners` and `source_path` read from the frontmatter lines
    `owners: [a, b]` and `source_path: <path>`, each a single line;
    either missing, or failing `provenance-writer`'s
    `interface/data/SealedProvenance.md` rules for that field, raises
    `ValueError`;
  - `source_hash` is `"sha256:"` plus the SHA-256 over every file under
    `<repo_root>/<source_path>`, recursively, except any directory named
    `__pycache__` and any file named `.sealed-provenance.json`, taken in
    sorted order of posix path relative to `source_path`, feeding each
    file's relative path as UTF-8, a NUL byte, the file's bytes, and a
    NUL byte. A missing directory hashes as no files;
  - `verifier_version` is `verifier-orchestrator`'s `GATE_VERSION`.

  It MUST NOT write anything. This is the one definition of a sealed
  component's key, as `current_provenance_key` is of a generated
  component's (`D163`, `D170`).
