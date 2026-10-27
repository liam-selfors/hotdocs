# CLI

None (`D92`). `provenance-tracker`'s `hotdocs build` is the one
developer-facing verb now — it calls `run_capability_gates` internally,
for every capability whose `realizes`-set is fully covered by the
current scope. A developer never invokes this component by name.
