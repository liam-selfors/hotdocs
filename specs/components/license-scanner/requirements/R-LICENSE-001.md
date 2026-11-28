# R-LICENSE-001

**R-LICENSE-001** — The scanner MUST compute a similarity score between
  `gen/<component>/`'s content and the reference corpus using k-gram
  (shingle) hashing of overlapping **9-token** windows, exactly as
  `interface/data/ReferenceCorpus.md`'s window hashing gives.
  A score at or above the configured **block threshold** MUST block the
  merge the same way a failed test does; no human sign-off can override
  it. Blocking is a pure confidence determination, independent of which
  entry matched or how risky it is (`R-LICENSE-003`).

  **Where the corpus lives** (`D51`): `VAR-LICENSE-CORPUS-PATH`, never
  `.hotdocs/`.
