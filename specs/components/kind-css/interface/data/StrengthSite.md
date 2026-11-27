```json
{"description": "2: color removed", "offset": 6, "end": 17, "property": "color"}
```

A plain `dict` with exactly these four keys; the example is the one
site of the file `a {\n  color: red;\n}\n`.

- `description`: `<line>: <property> removed`, `<line>` the property's
  line.
- `offset`: the character offset of the declaration's first character,
  the property's.
- `end`: the offset just after its `;`, or of the block's `}` when it
  has none, so the mutant is `text[:offset] + text[end:]`.
- `property`: the property as written, stripped.
