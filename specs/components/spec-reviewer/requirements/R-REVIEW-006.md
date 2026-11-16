# R-REVIEW-006

**R-REVIEW-006** — `glossary_judge(model, llm_backend)` MUST return a
  callable `judge(term, local_text, glossary_text)` that makes exactly one
  `complete(prompt, model, backend=llm_backend)` call, its prompt holding
  `term`, `local_text` and `glossary_text`, and returns
  `(conflicts, rationale)` when the reply's text from its first `{` to its
  last `}` parses as an object with a bool `conflicts` and a string
  `rationale`. For any other reply, or one carrying a `model_call_error`,
  it returns `None`. With a `model`, `check` passes this judge to `lint`;
  without one it passes `judge=None`.
