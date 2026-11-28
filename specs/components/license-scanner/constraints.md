# License Scanner — Non-Functional Constraints

- **Determinism.** Same `gen/<component>/` content and the same reference
  corpus version MUST always produce the same `similarity_score`.
- **No model calls.** Pure hashing/comparison logic.
- **Reference-corpus confidentiality.** The corpus of known-licensed-code
  fingerprints MAY itself be sensitive — this component MUST only ever compare against
  precomputed hashes, never embed or expose the reference corpus's raw
  source in `LicenseScanResult` or logs.
