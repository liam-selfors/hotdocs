# How the tool bootstrapped itself

A non-normative account of how each of the tool's own components first got real code, moved here from `README.md` for the MVP release. The decision records it cites are in `specs/decisions/`; each component's `verification/<slug>/BOOTSTRAP.md` has the full story. Counts and scores below are as of the round that first landed each component; several have been regenerated since (`D163`, `D199`–`D201`).

**There is no orchestrating "merge" component.** An earlier design had
one (`merge-orchestrator`) automatically generate, verify, and scan
every impacted component as part of attempting a merge; that design was
deliberately reversed (`D86`/`D87`), briefly consolidated into one
command (`D92`), then split back into two independently runnable
commands (`D93`). A developer runs `hotdocs generate <component-id>
--model=...` to deliberately produce or refresh one component's `gen/`
content and provenance, in `depends_on` order across a multi-component
change; separately, `hotdocs verify [--changed=...] [--model=...]`
checks every component in scope read-only (never triggering generation
as a side effect) and checks-then-runs every intersecting product
capability's scenarios (since that never produces new code), reporting
one ready/not-ready verdict before committing directly.
`provenance-tracker` (a live query, not a log of past attempts) and its
interactive graph UI answer "is everything ready" at any point, for a
given blast radius or the whole corpus.

**All twenty-five have real code**, and the central claim
this repo exists to test — that a real generation pipeline can
cold-regenerate a component from its spec, verified, with no human
hand-writing the result — is no longer theoretical:

- `spec-linter`, `graph-query-engine` — hand-authored bootstrap, standing
  in for the generator this pipeline didn't have yet when they were built.
- `cache-manager` — also hand-authored, but a temporary exception:
  nothing stops a real `generator` from cold-regenerating it later.
- `llm-endpoint`, `generator` — hand-authored, but *permanent* exceptions:
  each is what the other dispatches through, so neither could ever be
  produced the normal way *first*.
- `corpus-graph-builder`, `capability-scenario-verifier`,
  `impact-analyzer`, `license-scanner`, `secret-scanner`,
  `provenance-checker`, `docs-site-renderer`, `test-author`,
  `verifier-orchestrator`, `spec-bundle-assembler`,
  `provenance-tracker`, `provenance-writer`,
  `decision-drift-detector`, `review-packet-builder`,
  `spec-completeness-assistant`, `provenance-tracker-ui`,
  `component-gate-runner`, `hotdocs-cli`, `hotdocs-init` — cold-generated,
  not hand-written: a
  real model call, through a real `generator`
  dispatching through a real `llm-endpoint`, from each component's own
  assembled spec bundle and nothing else. `verifier-orchestrator` in
  particular took three real
  generation attempts, each failure traced to a genuine, previously
  undocumented spec gap (how a dependent locates a sealed sibling
  module; interface-drift's exact scope; a result field's required
  type) and fixed at that root cause before retrying — never patched
  by hand. `spec-bundle-assembler` closed its own "temporary
  exception" the same way (`D100`–`D109`): 14 of 15 criteria pass, one
  documented known limitation, full account in
  `verification/spec-bundle-assembler/BOOTSTRAP.md`. `provenance-tracker`
  took over thirty decisions to land (`D95`–`D127`), most of them
  fixing real defects in its dependencies rather than itself —
  `verifier-orchestrator`'s own `dependency_interfaces` gap and
  mutation-score averaging bug, `test-author`'s own fake-arity alias
  resolution — and first landed at 5 of 7 with two known limitations,
  both closed when it was regenerated for `D163` (7 of 7), full
  account in `verification/provenance-tracker/BOOTSTRAP.md`.
  `provenance-writer` took six rounds (`D128`–`D132`) but lands clean
  at 17 of 17, `mutation_score=0.8` — every round's failure a single,
  precisely diagnosed root cause (mutation testing itself caught a
  real gap twice: an entirely untested CLI entry point, and a
  `_to_jsonable` helper missing a data shape), full account in
  `verification/provenance-writer/BOOTSTRAP.md`. `decision-drift-
  detector` took eleven rounds (`D133`–`D137`) but lands clean at 5 of
  5, `mutation_score=0.84` — its criteria were mis-declared `kind:
  compiled` when `criterion-compiler`'s fixed step grammar can't
  express the real git repos these tests genuinely need, and most
  other rounds were either a real gap in a sibling component
  (`graph-query-engine`'s own undocumented DuckDB extension
  incantation) or thin scenario coverage rather than a true defect,
  full account in `verification/decision-drift-detector/BOOTSTRAP.md`.
  `review-packet-builder` took the most real rounds of any component
  this corpus has bootstrapped — roughly fifty, across sixteen
  decisions (`D138`–`D153`) — lands clean at 12 of 12,
  `mutation_score=0.82`. Most of that was one recurring defect
  resurfacing in new shapes: detecting a genuine `sealed:` transition
  correctly across every real git-history topology (a single commit,
  a feature branch, several commits with no feature branch at all)
  took four distinct corrections before one held for all of them —
  comparing each file against its own first commit in `HEAD`'s
  history, independent of the PR's own diff-base entirely — plus a
  markdown-rendering ambiguity (a nested per-entry sub-heading is
  indistinguishable from a section boundary to a generic parser) that
  broke generated tests across several separate rounds before being
  designed out. Full account in
  `verification/review-packet-builder/BOOTSTRAP.md`.
  `spec-completeness-assistant` (`D155`–`D157`, `D160`) and
  `provenance-tracker-ui` (`D154`, `D161`) both land clean, at
  `mutation_score` 0.81 and 0.95. Building them also exposed a hang in
  `verifier-orchestrator`'s own mutation gate — a mutant that never
  terminated, with no timeout to stop it — fixed there first
  (`D158`/`D159`). Each component's last gap was the same one three
  earlier components had: an untested CLI. Full accounts in each
  component's `BOOTSTRAP.md`.
- `component-gate-runner`, the last unbuilt component, landed at 13 of
  13 (`D166`). Auditing its spec before the first build found that
  nothing `hotdocs generate` wrote could ever have satisfied `hotdocs
  verify`: two components computed the provenance key differently.
  `D163` gave the key one owner, `provenance-checker`, and regenerated
  `verifier-orchestrator`, `license-scanner`, `secret-scanner`,
  `provenance-checker`, and `provenance-tracker` against it. The first
  real end-to-end `hotdocs generate`, on a throwaway copy, then found
  `generator` had never put `spec_bundle_hash` on its result — a test
  failure long filed as "pre-existing" (`D167`). Fixed, the round trip
  holds: `generate` writes provenance that `verify`'s own check reports
  as a hit, and a second `generate` short-circuits on it.

Once that real chain existed, the obvious next question was testable
directly: can a bootstrapped component regenerate *itself*, resolving the
generator/llm-endpoint chicken-and-egg problem the way a compiler
bootstraps by compiling itself once a first version exists by other
means? **Yes** — `llm-endpoint` has cold-regenerated itself twice,
through its own prior version, replacing it each time only because the
result passed every one of its own acceptance criteria (then
`D34`/`D35`, after two real failures the process itself surfaced: a
timeout bound too short for a larger component's spec bundle, and a
genuine tool-access/repo-context contamination the fix had to close
structurally, not just in a prompt). The same experiment attempted on
`generator` itself produced a plausible candidate that failed to import
— a real dependency-layout assumption two independently-generated
components hadn't yet had to agree on — and was correctly **not** swapped
in (`D46`). Both outcomes are the methodology working as intended: a
generation attempt earns its place by passing verification, not by
merely completing.

`pipeline/` — the directory that would hold frozen prompts and model
pins once they're shared by more than one caller — stays intentionally
thin for now (`D4`/`D6`); `criterion-compiler`, the one deliberately
permanent gap in this chain, remains unbuilt by design (sealed,
`specs/components/criterion-compiler/component.md` — trusting a
`compiled` criterion requires the compiler that compiles it to never
itself be agent-generated).
