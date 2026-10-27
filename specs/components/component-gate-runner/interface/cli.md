# CLI

None (`D92`). `provenance-tracker`'s `hotdocs build` is the one
developer-facing verb now — it calls `run_component_gates` internally,
for every component in scope. A developer never invokes this component
by name.
