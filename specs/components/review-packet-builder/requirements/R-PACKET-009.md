# R-PACKET-009

**R-PACKET-009** — A packet MUST be produced for every merge, including a
  fully clean one with no flags or warnings — never skipped, so the review
  habit stays consistent merge to merge rather than only appearing when
  something is wrong.

  This MUST hold even when `repo_root` is not a git repository at
  all, not only when it is one with zero commits — every git call
  this component makes (for `spec_diff`/`R-PACKET-001` and
  `exemption_changes`/`R-PACKET-007` specifically) MUST tolerate
  failure by treating the result as empty, never letting a git
  failure raise out of `build_review_packet` and abort the whole
  packet. Every other field (`changed_requirements`,
  `regenerated_components`, `verification_results`,
  `compliance_flags`, `provenance_hit_status`,
  `capability_scenarios`) depends on `changed_ids` and
  `provenance-tracker` alone, never on git, and MUST still be
  produced correctly regardless of `repo_root`'s own git state.
