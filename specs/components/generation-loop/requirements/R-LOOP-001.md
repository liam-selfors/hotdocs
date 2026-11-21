# R-LOOP-001

**R-LOOP-001** — Each attempt MUST generate first, with the mode's
  function and that attempt's feedback. A result with `refused` ends the
  loop at once with `stop_reason` `refused`, outcome `refused`. A result
  with a `model_call_error` is outcome `generation_failed`, its category
  recorded as `error_category`; the loop makes another attempt only when
  that category is in `RETRIED_CATEGORIES`, and otherwise ends with
  `stop_reason` `not_retried`.
