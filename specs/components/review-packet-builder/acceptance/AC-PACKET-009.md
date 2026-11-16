# AC-PACKET-009

Covers: R-PACKET-009
Kind: generated-test

```gherkin
Given a merge with zero flags, zero warnings, and full provenance hits
When build_review_packet runs
Then a packet is still produced, not skipped

Given a freshly git-init'd repo with zero commits at all (no HEAD to
  resolve yet)
When build_review_packet runs
Then a packet is still produced, with spec_diff and exemption_changes
  both empty rather than raising

Given a repo_root that is not a git repository at all (no .git
  directory, not even git-init'd), with a provenance-tracker fake
  installed
When build_review_packet runs
Then a packet is still produced -- changed_requirements,
  regenerated_components, verification_results, compliance_flags,
  provenance_hit_status, and capability_scenarios are all populated
  correctly from provenance-tracker, and spec_diff/exemption_changes
  are empty rather than raising
```
