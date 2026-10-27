# R-LICENSE-001

**R-LICENSE-001** — The scanner MUST compute a similarity score between
  `gen/<component>/`'s content and the reference corpus using k-gram
  (shingle) hashing: normalize source (strip whitespace/comments), tokenize,
  hash overlapping **9-token** windows, and compute the Jaccard-style ratio
  of matching window-hashes against the reference corpus's precomputed hash
  sets. A score at or above the configured **block threshold** MUST cause
  the merge to be blocked, the same way a failed test does — no human
  sign-off is required or able to override this. Block is a pure confidence
  determination, independent of which reference entry matched or how risky
  it is — that's R-LICENSE-003's job, not this one's.

  **Resolves the k-gram window size:** 9 tokens — large enough that one
  shared keyword or identifier (common even between independently-written
  code) can't trigger a window match by itself, small enough that a
  genuinely copied passage of a few lines still produces many overlapping
  matching windows, tolerant of a few differing tokens rather than needing
  an exact run.

  **Resolves the reference-corpus format:** the corpus MUST be a set of
  **precomputed k-gram hashes plus metadata** (`license_family`,
  `risk_tier`, a reference id — `R-LICENSE-003`), never raw licensed
  source text. This component MUST source that corpus from a maintained,
  continuously-updated external reference set, not a one-time, hand-curated
  list frozen into this spec or this component's own code — license
  fingerprints for actively-maintained OSS projects change as those
  projects evolve, and a frozen snapshot would silently stop catching real
  matches without ever reporting that it had gone stale. Raw license text
  is deliberately never stored here even transiently: this repo has no
  business holding a copy of copyrighted source merely to scan against it,
  and a precomputed hash set never needs to.

  **Where the corpus lives** (`D51`): `VAR-LICENSE-CORPUS-PATH`, never
  `.hotdocs/` — `.hotdocs/` is gitignored and local-only
  (`SPEC_GUIDELINES.md` §1), and this corpus's content directly
  determines `blocked`, a gate's pass/fail decision, which that same
  section forbids depending on anything there. A missing or
  unreachable corpus (the var absent, or its target unreadable) MUST
  still produce a real, recorded clean result — never an error, never
  a silently-skipped scan.

