# R-GEN-021

**R-GEN-021** — `generate()` MUST reject an incomplete reply before
  writing or caching anything, checking in this order:

  1. a reply with no `BEGIN FILE` line at all is `R-GEN-008`'s
     `empty_response`, whether or not it ends with the sentinel;
  2. a `BEGIN FILE` line with no matching `END FILE` line after it gives
     `model_call_error` `{"category": "truncated_response", "message": ...}`,
     the message naming that file's path;
  3. otherwise, a reply with no line `-----END REPLY <nonce>-----` gives
     `truncated_response`, the message saying the end marker is missing;
  4. a reply whose files hold neither `<module>.py` nor
     `<module>/__init__.py`, `<module>` the component's slug with hyphens
     replaced by underscores, gives `missing_module`.
