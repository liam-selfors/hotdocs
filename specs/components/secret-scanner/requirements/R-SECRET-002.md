# R-SECRET-002

**R-SECRET-002** — A scan with at least one match MUST report `flagged`
  `true`, and `main` MUST then exit `1` (`interface/cli.md`). Flagging
  is a pure confidence determination (did a detector match at all),
  independent of the rule's risk, which is `R-SECRET-004`'s concern.
  Whether a flagged scan stops a merge is decided by `hotdocs verify`
  (`R-TRACK-016`), with no human sign-off able to override it (`D378`).
