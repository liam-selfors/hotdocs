# R-IMPACT-002

**R-IMPACT-002** — For a changed component, if `component.md`
(Purpose/Scope/Definitions), `requirements/`, `constraints.md`, or
`acceptance/` is what changed, and neither `interface/cli.md`,
`interface/library.md`, nor any file under `interface/data/` changed (per
R-IMPACT-003), the analyzer MUST NOT include that component's dependents in
the blast radius on that basis — such a change is internal and MUST NOT
propagate (`D1`). (`interface/guarantees/` changes are handled separately
by R-IMPACT-008 (`D2`), not by this requirement.)
