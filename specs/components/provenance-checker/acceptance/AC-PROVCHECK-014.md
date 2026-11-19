# AC-PROVCHECK-014

Covers: R-PROVCHECK-009
Kind: generated-test

Fixture and the expected value E: `testing.md`, "A fake asset kind".

```gherkin
When current_provenance_key("comp-foo", repo_root) is called
Then its assets is exactly E

Given a manifest with spec_bundle_hash H and assets E
When check_provenance("comp-foo", "H", {}, repo_root) is called
Then hit is true and reason is null

Given that manifest, and separately: the definition file's bytes
  changed; the adapter's provision reporting versions {"fakec": "2.1.0"}
Then hit is false and reason is "assets differ"

Given the adapter's provision reporting ok false and reason
  "fake needs fakec >= 2"
Then hit is false and reason is "fake needs fakec >= 2"

Given comp-foo declaring [nokind:static/b.x] instead
Then hit is false and reason is "unknown asset kind: nokind"

Given a manifest with no assets field
Then hit is false and reason is "assets differ"; and with comp-foo
  declaring no assets, the same manifest is a hit

Given the manifest's spec_bundle_hash is "OTHER"
Then reason is "spec_bundle_hash differs" and provision was not called
```
