# Test Supply — Non-Functional Constraints

- **Never writes under `verification/`** except `discard`'s deletion: an
  authored test is written to a temporary directory, so a stale or
  probe-failed committed file stays on disk until it is discarded.
