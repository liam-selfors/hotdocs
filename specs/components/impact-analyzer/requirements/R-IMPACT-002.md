# R-IMPACT-002

**R-IMPACT-002** — For a changed component, if `component.md`
(Purpose/Scope/Definitions), `requirements/`, `constraints.md`, or
`acceptance/` is what changed, and neither `interface/cli.md`,
`interface/library.md`, nor any file under `interface/data/` changed (per
R-IMPACT-003), the analyzer MUST NOT include that component's dependents in
the blast radius on that basis — such a change is internal and MUST NOT
propagate. (`interface/guarantees/` changes are handled separately by
R-IMPACT-008, not by this requirement.)

**This distinction was not previously specified anywhere in
`notes/initial-ideas.md` or `SPEC_GUIDELINES.md` before this spec was
originally written** — D2 states it only as a *sizing heuristic* ("a
typical spec change stays inside the component's own bundle and does not
force an edit to a depended-upon interface"), not as an executable rule
for this component. This requirement is the first place it becomes a
real, testable behavior rather than an aspiration.

**D15 update:** originally this rule compared `interface.md` as one
whole file, hashed byte-for-byte — correct but blunt (a purely cosmetic
edit anywhere in the file still forced full propagation), and a later
working session explored section-scoped hashing as a refinement before
settling on the one-file-per-unit redesign (D15) instead, which achieves
the same precision — a prose-only edit to, say, `interface/library.md`'s
explanatory text still counts as that file changing, same as before, but
a change entirely confined to `requirements/`/`acceptance/`/
`constraints.md`/`component.md`'s narrative sections no longer touches
`interface/` at all and so no longer forces propagation. No new parsing
logic was needed to get this — directory structure already *is* the
section boundary.

**D16 update:** split `interface/guarantees/` out from this requirement's
scope into its own, separately-narrowable requirement (R-IMPACT-008) —
behavioral guarantees are the one part of `interface/` where "a dependent
only cares about some of this" is a coherent claim; `cli.md`/`library.md`/
`data/*.md` stay coarse, always-propagating, under R-IMPACT-003.
