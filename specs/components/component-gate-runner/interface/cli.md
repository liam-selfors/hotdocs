# CLI

```
hotdocs generate <component-id> --model=<model-id> [--seed=<n>] \
  [--retry-feedback=<R-id>,...] [--max-attempts=<n>] [--mode=single|agentic] \
  [--allow-unisolated-exec] [--repo-root=<dir>] [--format=json|text]
```

The one command a developer uses to (re)generate a component, distinct
from `hotdocs verify`'s read-only check (`D91`/`D93`). Run it across a
multi-component change in `depends_on` order; this component does not
sequence multiple calls itself (`R-ASSEMBLE-011`).

`main(argv)` receives `argv` beginning `["generate", <component-id>,
...]`. Every flag takes its value either as `--flag=value` or as the
next argument.

- `<component-id>` — `comp-<slug>`; it must have a
  `specs/components/<slug>/component.md` under `--repo-root`.
- `--model` — required, no default (`R-GATE-002`).
- `--seed` — integer, default `0`.
- `--retry-feedback` — comma-separated `R-id`s, passed to
  `run_component_gates` as a list; omitted means `None`.
- `--max-attempts` — integer, at least `1`, default `3` (`R-GATE-010`).
- `--mode` — `single` (default) or `agentic` (`R-GATE-010`).
- `--allow-unisolated-exec` — takes no value; lets agentic mode run the
  model's code with no OS sandbox.
- `--repo-root` — default the current directory.
- `--format` — `json` prints the `ComponentPipelineResult` as JSON,
  converting each nested value recursively: an object with `to_dict()`
  through it, a dataclass via `dataclasses.asdict`, any other object
  via `vars()`;
  `text` (default) prints the component id, `provenance hit` or the
  `block_reason` (`passed` when not blocked), one line per attempt,
  `attempt <number>: <outcome>`, and each scan's
  `blocked`/`flagged`; then `model_call_error: <category>: <message>`
  when one is set, and `license_scan not evaluated: <reason>` when the
  license scan's `evaluated` is false (read with dual dict-or-attribute
  access).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | The gauntlet concluded — a hit, a pass, or a verification failure alike. |
| `1` | `block_reason` is `"model_call_error"`. |
| `2` | Usage error: a missing `<component-id>` or `--model`, an unknown component, a non-integer `--seed`, a `--max-attempts` that is not an integer of at least `1`, an invalid `--format` or `--mode`, an invalid `[generate]` value, an unknown argument, a wrong first word, or a flag given last with no value. |
