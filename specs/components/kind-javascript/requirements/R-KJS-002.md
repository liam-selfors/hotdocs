# R-KJS-002

**R-KJS-002** — `layout_errors(asset_file)` MUST return a list of
messages, empty when the layout is valid, built as follows:

1. If the file's bytes are not valid UTF-8, the result is exactly
   `["parse error: not UTF-8"]` and nothing else runs.
2. Parse check: the file is copied to `<tmp>/<stem>.mjs` (`<stem>` the
   asset's file name without its suffix) and `node --check <copy>` runs
   (`interface/library.md`, "Finding node"). A non-zero exit gives
   `parse error: <line>`, where `<line>` is the first stderr line that
   starts with `SyntaxError:`, else the first non-empty stderr line,
   stripped. A timeout gives `parse error: timed out after 30 seconds`.
   With no `node` found, the message is `javascript needs node >= 24`.
3. Forbidden tokens, over the scan's tokens in text order, one message
   per occurrence: a name token `import` gives `forbidden: import`; a
   name token `require` or `fetch` whose next token is `(` gives
   `forbidden: require(` or `forbidden: fetch(`; a name token
   `XMLHttpRequest` or `WebSocket` gives `forbidden: <name>`. Text inside
   strings and comments is never a token, so it is never forbidden.

The parse-check message, if any, comes first, then the forbidden
messages.
