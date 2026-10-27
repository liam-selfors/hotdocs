# Bootstrap Account: `generator`

A seventh hand-authored bootstrap exception — but structurally permanent
like `llm-endpoint`, not temporary like `cache-manager`/
`spec-bundle-assembler`: `generator` is the component that does the
cold-regenerating, so nothing could ever have cold-regenerated it first,
even once this file makes real generation possible for everything else.

**Two real, pre-existing interface gaps found while wiring this for
real**, both fixed:

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
corpus, both superseded by `D3`'s retirement of the best-of-k retry
loop; nothing to test against). None of this component's own
verification requires a real model call.

The real end-to-end integration — a genuine cold-generation attempt
against the real corpus, through this exact code — is the self-hosting
experiment this component's own decision history records, not repeated
here.

**This component was itself the target of a real self-regeneration
attempt** — a well-architected five-file candidate came back,
but failed to import (it assumed `cache-manager` was a package with a
`.data` submodule; the real one is a flat module) and was correctly
rejected rather than swapped in. `gen/generator/generator.py` is still
this file, unchanged. See `notes/backlog.md` for the generalizable
import-path gap it exposed.

**`D37` closes that gap, one-directionally.** `_build_prompt` now
includes `bundle.dependency_usage` (`R-ASSEMBLE-011`) as its own
section (`R-GEN-013`) — real, introspected import facts about each
dependency's current code, never anything about how *this* component's
own dependents use it (that direction was considered and rejected, see
`D37` for why). `PROMPT_VERSION` bumped to `v2` since the template text
changed.

**Two further real bugs** were found re-attempting the
self-regeneration with that fix in place: a self-referential
delimiter collision unique to this one component (fixed with a per-call
nonce, `D38`), a degenerate empty-files result silently poisoning the cache
(fixed by caching only non-empty results, `D39`), an undocumented
`cache-manager` payload schema (documented in
`interface/data/CachedResult.md`, `D40`), and a real crash in one
candidate's dynamic dependency-loading technique that omitted
registering the loaded module in `sys.modules` before running its code
(documented as `R-GEN-014`, `D41`).

**`D42`: this file is no longer this component's installed code.** A
fourth real retry, with every fix above in place, produced a complete,
537-line candidate that passed all 12 of this component's own
`AC-GEN-*` criteria for real (including the new `AC-GEN-015`, which
specifically exercises the exact crash the previous attempt hit) — the
first time this component's own self-regeneration has actually closed
the loop. `gen/generator/generator.py` is now that candidate, not this
hand-authored bootstrap; `verification/generator/conftest.py` and
`test_generator.py` were rewritten to match its conventions (the nonce
lives directly in the prompt, not a separate `system_prompt` parameter;
dependencies load dynamically from `repo_root` per call rather than via
a static `sys.path` entry). This file is kept as the historical record
of how `generator` came to exist and what each real attempt against it
found — not as a description of the code currently installed.
