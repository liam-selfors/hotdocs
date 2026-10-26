# Bootstrap Account: `generator`

A seventh hand-authored bootstrap exception — but structurally permanent
like `llm-endpoint`, not temporary like `cache-manager`/
`spec-bundle-assembler`: `generator` is the component that does the
cold-regenerating, so nothing could ever have cold-regenerated it first,
even once this file makes real generation possible for everything else.

**Two real, pre-existing interface gaps found while wiring this for
real**, both fixed (`D50`):

- `generate()` had no `repo_root` parameter, yet `R-GEN-009`'s
  sealed/pinned-override precondition check needs to read a component's
  real `component.md` frontmatter and `gen/<component>/.overrides.json`
  directly — `SpecBundle`'s own `spec` field excludes frontmatter by
  construction (`R-ASSEMBLE-001`), so there was never a path from the
  bundle alone to this information.
- `generate()` had no injectable-backend parameter, yet every one of
  this component's own acceptance criteria (`AC-GEN-001`–`013`) already
  required "an injected mock model." Added `llm_backend`, passed
  straight through to `llm-endpoint`'s own `backend` parameter — the
  same dependency-injection seam, not a second one.

**A third gap found one level down**: `cache-manager`'s `CachedResult`
schema listed five known `gate_type`s, and `generator` was never one of
them — even though `cache-manager`'s own `Purpose` names `generator` as
a consumer. Added `"generator"` as a sixth type, with a minimal shape
fingerprint (`component_id`/`model`/`prompt_version`/`files`) matching
`GenerationResult`'s own shape.

**`R-GEN-009`'s pinned-override check is whole-component, not
per-file** — a deliberate, documented interpretation: `R-GEN-009`'s own
prose describes a per-file exemption (don't overwrite a *specific*
pinned file), but `AC-GEN-009`'s own Gherkin tests a simpler, more
conservative behavior — any non-empty `.overrides.json` refuses
generation for that *whole* component. Implemented the conservative
version the acceptance criterion actually demands: never risk
overwriting a pinned file by not generating anything for that component
at all, rather than building a more granular partial-overwrite
mechanism nothing here yet asks for.

Verified entirely on an injected mock backend, at zero cost: all 10
tests pass (one per `AC-GEN-*` criterion with a defined acceptance
file — `R-GEN-007`/`010` have no corresponding `AC-GEN-*` file in this
corpus, both superseded by `D31`'s retirement of the best-of-k retry
loop; nothing to test against). None of this component's own
verification requires a real model call.

The real end-to-end integration — a genuine cold-generation attempt
against the real corpus, through this exact code — is the self-hosting
experiment recorded in `specs/decisions/D51.md`, not repeated here.

**This component was itself the target of a real self-regeneration
attempt (`D54`)** — a well-architected five-file candidate came back,
but failed to import (it assumed `cache-manager` was a package with a
`.data` submodule; the real one is a flat module) and was correctly
rejected rather than swapped in. `gen/generator/generator.py` is still
this file, unchanged. See `D54` for the full account and
`notes/backlog.md` for the generalizable import-path gap it exposed.

**`D55` closes that gap, one-directionally.** `_build_prompt` now
includes `bundle.dependency_usage` (`R-ASSEMBLE-011`) as its own
section (`R-GEN-013`) — real, introspected import facts about each
dependency's current code, never anything about how *this* component's
own dependents use it (that direction was considered and rejected, see
`D55` for why). `PROMPT_VERSION` bumped to `v2` since the template text
changed. A real re-attempt of `generator` regenerating itself, with
this fix in place, is tracked as the natural next verification step —
not done here, to keep this decision's own implementation verified on
its own terms first.
