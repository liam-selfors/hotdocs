# R-LICENSE-001

**R-LICENSE-001** — The scanner MUST compute a similarity score between
  `gen/<component>/`'s content and the reference corpus using k-gram
  (shingle) hashing: normalize source (strip whitespace/comments),
  tokenize, hash overlapping **9-token** windows, and compute the ratio
  of matching window-hashes against the corpus's precomputed hash sets.
  A score at or above the configured **block threshold** MUST block the
  merge the same way a failed test does; no human sign-off can override
  it. Blocking is a pure confidence determination, independent of which
  entry matched or how risky it is (`R-LICENSE-003`).

  **Window size:** 9 tokens — large enough that one shared keyword or
  identifier cannot trigger a match, small enough that a copied passage
  of a few lines still yields many matching windows.

  **Corpus format:** a set of **precomputed k-gram hashes plus
  metadata** (`license_family`, `risk_tier`, a reference id), never raw
  licensed source, sourced from a maintained external reference set and
  never a one-time list frozen into this spec or code.

  **Where the corpus lives** (`D51`): `VAR-LICENSE-CORPUS-PATH`, never
  `.hotdocs/` (gitignored and local-only, `SPEC_GUIDELINES.md` §1, which
  forbids a gate's pass/fail depending on it). A scan with no usable
  corpus is never reported as a clean pass: `R-LICENSE-010`/`011`.
