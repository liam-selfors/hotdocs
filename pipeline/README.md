# Pipeline

Workflow definitions, frozen prompts, and pinned models that govern
generation and verification. No repo-wide toggles currently exist — this
build is single-model only; the second-model toggles
(`cross_model_divergence_check`, `fallback_standby_build`) that used to
live here are removed from the active scope for now, see
`notes/initial-ideas.md` §14 ("Future enhancements").

See `SPEC_GUIDELINES.md` §6 (verification gates).

_Nothing here yet — this is the linter + generation/verification pipeline
itself, the next prototype step after the example project (see
`notes/initial-ideas.md` §10)._
