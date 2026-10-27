# hotdocs

An experiment in **spec-driven agentic development**: a way of building software
where the primary change-tracked assets are plain-text specification documents,
and code, tests, and configuration are regenerated from those specs by coding
agents running in a CI/CD pipeline.

The bet: if the specification corpus is structured strictly enough and its
acceptance criteria are strong enough, we can trust an automated pipeline to
produce the code — and human review can shift from reviewing diffs of code to
reviewing diffs of intent.

## Status

The rules are formalized (`SPEC_GUIDELINES.md`), and the repository's own
pipeline is itself the worked example: **23 components, fully specced**
under `specs/components/` (component anatomy, requirements, interfaces,
acceptance criteria, constraints — see `specs/architecture/
pipeline-decomposition.md` for the full decomposition), covering lint,
blast-radius analysis, generation, verification, compliance scanning,
provenance, and a DuckDB-backed query layer shared across several of them
(`specs/architecture/graph-query-engine.md`).

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

**Sixteen of those components have real code**, and the central claim
this repo exists to test — that a real generation pipeline can
cold-regenerate a component from its spec, verified, with no human
hand-writing the result — is no longer theoretical:

- `spec-linter`, `graph-query-engine` — hand-authored bootstrap, standing
  in for the generator this pipeline didn't have yet when they were built.
- `cache-manager`, `spec-bundle-assembler` — also hand-authored, but
  temporary exceptions: nothing stops a real `generator` from
  cold-regenerating either, later.
- `llm-endpoint`, `generator` — hand-authored, but *permanent* exceptions:
  each is what the other dispatches through, so neither could ever be
  produced the normal way *first*.
- `corpus-graph-builder`, `capability-scenario-verifier`,
  `impact-analyzer`, `license-scanner`, `secret-scanner`,
  `provenance-checker`, `docs-site-renderer`, `test-author`,
  `verifier-orchestrator` — cold-generated, not hand-written: a real
  model call, through a real `generator` dispatching through a real
  `llm-endpoint`, from each component's own assembled spec bundle and
  nothing else. `verifier-orchestrator` in particular took three real
  generation attempts, each failure traced to a genuine, previously
  undocumented spec gap (how a dependent locates a sealed sibling
  module; interface-drift's exact scope; a result field's required
  type) and fixed at that root cause before retrying — never patched
  by hand.
- `component-gate-runner` and `capability-scenario-verifier`'s own
  provenance mechanism are fully specced but **not yet regenerated** —
  the next real components this corpus's own methodology needs to
  build for itself.

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

Decisions are tracked as formal ADRs in `specs/decisions/` (`D1`
through `D93` — `D1`–`D75` from the 2026-10 MVP baseline reset,
`D76` onward recorded normally since); `notes/initial-ideas.md`
holds the original brainstorm (its own frozen `D1`–`D30` historical
numbering, informal) plus the full discussion behind many of the
earlier decisions.

## Repository conventions

See `SPEC_GUIDELINES.md` for the full, enforceable rules. Summary:

| Path            | Purpose                                                        |
| --------------- | ------------------------------------------------------------- |
| `specs/`        | Normative specification documents — the source of truth.      |
| `gen/`          | Generated code. Not hand-edited (two declared exemptions only). |
| `pipeline/`     | Agent workflow definitions, frozen prompts, model pins, toggles. |
| `verification/` | Generated tests, contract checks, drift detection, corpus graph. |
| `tools/`        | Hand-written repo-maintenance/authoring scripts. Not spec-driven, not gated. |
| `notes/`        | Brainstorming and design discussion. Non-normative.           |
