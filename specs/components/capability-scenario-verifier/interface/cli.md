# CLI

None (`D92`, unreversed by `D93`). `provenance-tracker`'s `hotdocs
verify` is the one developer-facing verb that reaches this component —
it calls `run_capability_gates` internally, for every capability whose
`realizes`-set is fully covered by the current scope. A developer never
invokes this component by name.
