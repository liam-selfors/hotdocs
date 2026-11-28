# Review Packet Builder — Non-Functional Constraints

- **Determinism.** Given the same upstream results, the packet MUST be
  byte-identical across runs.
- **No network access, no model calls.** Pure formatting of already-
  computed data.
- **Readable by a human in the time it takes to review a spec diff.** Not a
  dump of every field every upstream component produced — organized into
  the sections R-PACKET-001–008 name, in that order.
