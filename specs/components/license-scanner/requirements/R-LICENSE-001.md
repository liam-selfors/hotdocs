# R-LICENSE-001

**R-LICENSE-001** — The scanner MUST compute a similarity score between
  `gen/<component>/`'s content and the reference corpus using k-gram
  (shingle) hashing: normalize source (strip whitespace/comments), tokenize,
  hash overlapping k-token windows, and compute the Jaccard-style ratio of
  matching window-hashes against the reference corpus's precomputed hash
  sets. A score at or above the configured **block threshold** MUST cause
  the merge to be blocked, the same way a failed test does — no human
  sign-off is required or able to override this. Block is a pure confidence
  determination, independent of which reference entry matched or how risky
  it is — that's R-LICENSE-003's job, not this one's.
