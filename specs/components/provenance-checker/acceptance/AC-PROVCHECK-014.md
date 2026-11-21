# AC-PROVCHECK-014

Covers: R-PROVCHECK-009
Kind: generated-test

Fixture and the expected values P and E: `testing.md`, "The fake `python`
adapter" and "A fake asset kind".

```gherkin
When current_provenance_key("comp-foo", repo_root) is called
Then its assets is exactly E

Given a manifest with spec_bundle_hash H and assets E
When check_provenance("comp-foo", "H", {}, repo_root) is called
Then hit is true and reason is null

Given that manifest, and separately: the definition file's bytes
  changed; a comment line appended to kind_fake.py, both after the
  manifest was written
Then hit is false and reason is "assets differ"

Given the adapter's provision reporting ok false and reason
  "fake needs fakec >= 2"
Then hit is false and reason is "fake needs fakec >= 2"

Given comp-foo declaring [nokind:static/b.x] instead
Then hit is false and reason is "unknown asset kind: nokind"

Given the python adapter's provision reporting ok false and reason
  "python environment: requirements.lock does not pin pytest"
Then hit is false, reason is that reason, and the fake adapter's
  provision was not called

Given comp-foo's component.md is removed
Then current_provenance_key's assets is exactly [P], and a manifest
  with assets [P] is a hit

Given comp-foo's component.md also has the line "sealed: true"
Then current_provenance_key's assets is [] and neither adapter's
  provision was called

Given a manifest with no assets field, or assets null
Then hit is false and reason is "assets differ", and so with comp-foo's
  component.md removed

Given the manifest's spec_bundle_hash is "OTHER"
Then reason is "spec_bundle_hash differs" and neither adapter's
  provision was called
```
