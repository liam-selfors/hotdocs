# R-GEN-021

**R-GEN-021** — Before any model call, `generate()` MUST return
  `check_asset_environment`'s category, if any, as the
  `model_call_error`, messages joined by `"\n"`. It MUST reject an
  incomplete reply before writing or caching anything, checking in this
  order:

  1. a reply with no `BEGIN FILE` line at all is `R-GEN-008`'s
     `empty_response`, whether or not it ends with the sentinel;
  2. a `BEGIN FILE` line with no matching `END FILE` line after it gives
     `model_call_error` `{"category": "truncated_response", "message": ...}`,
     the message naming that file's path;
  3. otherwise, a reply with no line `-----END REPLY <nonce>-----` gives
     `truncated_response`, the message saying the end marker is missing;
  4. a reply whose files hold neither `<module>.py` nor
     `<module>/__init__.py`, `<module>` the component's slug with hyphens
     replaced by underscores, gives `missing_module`;
  5. otherwise, `check_assets` on the files, paths as `R-GEN-015` strips
     them; a category it returns is the `model_call_error`'s, with its
     messages joined by `"\n"` as the message. It checks, the first
     failing step deciding (`specs/architecture/asset-kinds.md`, `D343`):
     1. each declared asset path not written, in declaration order, is
        `missing_asset`, message `missing asset: <path>`;
     2. each written path not ending in `.py` and not declared, sorted,
        is `malformed_layout`, message `undeclared file: <path>`;
     3. each message of each declared asset's adapter `layout_errors`,
        in declaration order, as `<path>: <message>`; any is
        `malformed_layout`;
     4. each message of the `python` adapter's `layout_errors` on the
        reply's `.py` files, written as one temporary code directory,
        as given; any is `malformed_layout` (`D344`).
