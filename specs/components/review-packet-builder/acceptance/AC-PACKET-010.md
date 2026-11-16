# AC-PACKET-010

Covers: R-PACKET-010
Kind: generated-test

```gherkin
Given a component whose generated code changed substantially
When build_review_packet runs
Then the packet contains no generated-code diff content anywhere in it
```
