# AC-PACKET-004

Covers: R-PACKET-004
Kind: compiled

```gherkin
Given a VerificationReport with one passing and one failing criterion
When build_review_packet runs
Then verification_results shows both results individually, not only an
  aggregate pass/fail
```
