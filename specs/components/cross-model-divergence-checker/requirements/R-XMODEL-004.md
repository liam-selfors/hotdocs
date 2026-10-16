# R-XMODEL-004

**R-XMODEL-004** — In `divergence` mode (`cross_model_divergence_check:
  enabled`): if the second candidate's verdict is `pass`, this component
  MUST compare its observable behavior against the canonical candidate's —
  running the same already-compiled/generated test inputs against both and
  diffing outputs. This comparison is deterministic once both candidates
  and the test inputs exist: no model or judgment is needed to tell whether
  two concrete outputs match.
