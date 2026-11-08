# AC-PACKET-013

Covers: R-PACKET-013
Kind: generated-test

```gherkin
Given a fake tool root <t> holding a byte-for-byte copy of this
  component's module (its source read once, when the test module is
  imported, from the normally imported module's __file__; never from a
  copy, which a test may delete) at
  <t>/gen/review-packet-builder/review_packet_builder.py and a
  provenance-tracker stand-in at
  <t>/gen/provenance-tracker/provenance_tracker.py reporting comp-tool
  as a provenance hit, and a repo_root that is a git repository with
  one commit and no gen/ directory
When that copy, loaded by file path, runs
  build_review_packet(["comp-tool"], repo_root)
Then provenance_hit_status is {"comp-tool": true}

Given the same, plus a repo_root/gen/provenance-tracker/ stand-in
  reporting comp-tool as a miss
When the copy runs build_review_packet(["comp-tool"], repo_root)
Then provenance_hit_status is {"comp-tool": false}
```
