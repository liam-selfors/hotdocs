# Pipeline

Workflow definitions, frozen prompts, and pinned models that govern
generation and verification. No repo-wide toggles currently exist — this
build is single-model only; the second-model toggles
(`cross_model_divergence_check`, `fallback_standby_build`) that used to
live here are removed from the active scope for now, see
`notes/initial-ideas.md` §14 ("Future enhancements").

See `SPEC_GUIDELINES.md` §6 (verification gates).

## Still empty — on purpose, for two different reasons

This directory holds `criterion-compiler/`'s own `source_path` (sealed,
by permanent design — trusting a `compiled` criterion requires the
compiler that compiles it to never itself be agent-generated,
`specs/components/criterion-compiler/component.md`). No file exists
there yet: `criterion-compiler` remains unbuilt, the one real gap left
in the generation chain this repo's own methodology now actually
exercises.

Everything else that would normally live here — frozen prompts, model
pins, retry policy — is real, but currently lives inline in each real
component's own `gen/` code (`generator.py`'s own `_SYSTEM_PROMPT`/
`PROMPT_VERSION`, `llm-endpoint`'s model-resolution logic) rather than
externalized into this directory, since no second caller or second
model has yet needed it factored out — the same anti-premature-
abstraction stance (`D4`/`D6`) this corpus applies everywhere else.
