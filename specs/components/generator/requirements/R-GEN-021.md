# R-GEN-021

**R-GEN-021** — `generate()` MUST reject an incomplete reply before
  writing or caching anything. A reply whose text has no line
  `-----END REPLY <nonce>-----`, or that has a `BEGIN FILE` line with no
  matching `END FILE` line after it, MUST give `model_call_error`
  `{"category": "truncated_response", "message": ...}`, the message
  naming the unclosed file's path when there is one. A reply whose files
  hold neither `<module>.py` nor `<module>/__init__.py`, `<module>` the
  component's slug with hyphens replaced by underscores, MUST give
  `model_call_error` `{"category": "missing_module", "message": ...}`.
