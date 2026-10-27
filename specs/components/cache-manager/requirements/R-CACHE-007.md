# R-CACHE-007

**R-CACHE-007** — `put` MUST reject (not silently accept) a result payload
  whose shape doesn't match the schema expected for the `gate_version`'s
  declared gate type — guards against cache poisoning from a caller bug
  writing, e.g., a `LintReport`-shaped payload under a `license_scanner`
  `gate_version`.

  **The six gate types' exact required payload keys** (`D56`, found
  missing from any spec — a real caller, writing against this
  component's real types, had no way to know these beyond reading this
  component's own Python source):

  | `gate_type` | Required top-level payload keys |
  | --- | --- |
  | `generator` | `component_id`, `model`, `prompt_version`, `files` |
  | `compiler` | `outputs`, `gate_version`, `summary` |
  | `generated_test` | `component_id`, `criterion_id`, `model`, `file` |
  | `llm_judge` | `result`, `rationale` |
  | `license_scanner` | `component_id`, `gate_version`, `similarity_score`, `blocked`, `matches` |
  | `secret_scanner` | `scope`, `gate_version`, `flagged`, `matches` |

  This is a deliberately shallow key-presence check, not a full
  JSON-schema validator (`BOOTSTRAP.md`) — extra keys are permitted;
  only a missing required key rejects a `put`.
