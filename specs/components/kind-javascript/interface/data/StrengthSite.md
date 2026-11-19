# `StrengthSite`

```json
{"description": "3: === -> !==", "offset": 57, "token": "===", "swap": "!=="}
```

A plain `dict` with exactly these four keys.

- `description`: `<line>: <token> -> <swap>`, with the token's line as
  the scan counts it.
- `offset`: the token's character offset in the file's decoded text.
- `token`: the token as written.
- `swap`: the text that replaces it in the mutant.
