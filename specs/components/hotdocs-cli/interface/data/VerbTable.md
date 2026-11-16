# `VerbTable`

The dispatcher's only knowledge of a verb (`R-CLI-001`). `strip` is how
many leading `argv` tokens are removed before the component's `main` is
called, because the components disagree about whether `main` wants its
verb words. `model` is `required` when the component cannot run without
`--model`, `optional` when it runs without one but does more with one,
and `no` otherwise (`R-CLI-003`). Entries in `module` containing a `.` are
packages' submodules.

| verb words | dir | module | strip | model | summary |
| --- | --- | --- | --- | --- | --- |
| `lint` | `gen/spec-linter` | `spec_linter` | 1 | no | validate the spec corpus |
| `impact` | `gen/impact-analyzer` | `impact_analyzer` | 1 | no | blast radius of a change |
| `assemble` | `gen/spec-bundle-assembler` | `spec_bundle_assembler` | 1 | no | build a component's spec bundle |
| `compile-criteria` | `pipeline/criterion-compiler` | `criterion_compiler` | 1 | no | compile the compiled criteria |
| `author-test` | `gen/test-author` | `test_author` | 0 | required | write one criterion's test |
| `verify-component` | `gen/verifier-orchestrator` | `verifier_orchestrator` | 1 | no | verify one component |
| `generate` | `gen/component-gate-runner` | `component_gate_runner` | 0 | required | generate and verify a component |
| `verify` | `gen/provenance-tracker` | `provenance_tracker` | 0 | optional | is everything ready |
| `track feedback` | `gen/provenance-tracker` | `provenance_tracker` | 0 | no | last failing requirements |
| `track ui build` | `gen/provenance-tracker-ui` | `provenance_tracker_ui` | 0 | optional | build the readiness page |
| `provenance check` | `gen/provenance-checker` | `provenance_checker` | 1 | no | is provenance a hit |
| `provenance write` | `gen/provenance-writer` | `provenance_writer` | 0 | no | write a provenance manifest |
| `license-scan` | `gen/license-scanner` | `license_scanner` | 1 | no | license scan one component |
| `secret-scan` | `gen/secret-scanner` | `secret_scanner` | 1 | no | scan for secrets |
| `review-packet build` | `gen/review-packet-builder` | `review_packet_builder` | 0 | no | build a review packet |
| `decision-drift` | `gen/decision-drift-detector` | `decision_drift_detector` | 0 | no | decisions out of step with specs |
| `decision-impact` | `gen/decision-drift-detector` | `decision_drift_detector` | 0 | no | what a decision touches |
| `docs-site build` | `gen/docs-site-renderer` | `docs_site_renderer.cli` | 2 | no | render the docs site |
| `corpus-graph build` | `gen/corpus-graph-builder` | `corpus_graph_builder.cli` | 1 | no | build the corpus graph |
| `assist` | `gen/spec-completeness-assistant` | `spec_completeness_assistant` | 1 | optional | review a spec change |
| `spec check` | `gen/spec-reviewer` | `spec_reviewer` | 2 | optional | check criteria from their test authors' view |
| `decision new` | `gen/spec-scaffolder` | `spec_scaffolder` | 0 | no | draft the next decision record |
| `decision ratify` | `gen/spec-scaffolder` | `spec_scaffolder` | 0 | no | ratify a decision record |
| `decision record-commit` | `gen/spec-scaffolder` | `spec_scaffolder` | 0 | no | record the commit that landed a decision |
| `component new` | `gen/spec-scaffolder` | `spec_scaffolder` | 0 | no | lay out a new component |
| `init` | `gen/hotdocs-init` | `hotdocs_init` | 1 | no | set up a new project |

`init` is special (`R-CLI-005`). `cache` is documented by
`cache-manager` but that component defines no `main`, so it has no row.
