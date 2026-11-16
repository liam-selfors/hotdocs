# R-AGENT-003

**R-AGENT-003** — `execute` MUST implement every tool exactly as
  `specs/architecture/agent-sandbox.md`'s Paths and Tools sections say:
  the path rules, the size and file-count limits, the 8192-character cut,
  the order calls are checked in, the error results, and `finish`'s
  effect on later calls. An unknown tool name or a missing argument (its
  key absent or its value not a string) is the error result
  `bad call: <reason>`, checked before the path rules. `execute` never
  raises.
