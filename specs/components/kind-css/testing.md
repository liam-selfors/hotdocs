Tests import the module as `import kind_css` and call its functions
directly; this component's own tests never use an `asset_runner`
fixture.

Fixtures: write each stylesheet with `path.write_text(text,
encoding="utf-8")` (or `write_bytes` where a criterion gives bytes)
under pytest's `tmp_path`, exactly as the criterion shows it, every
line ending in `\n`, and pass the `Path`.

Named fixtures, each written exactly as shown, every line ending in
`\n`:

- `s.css`:

  ```
  :root {
    --c-text: #1f2328;
    --c-bg: #ffffff;
    --c-gap: 8px;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --c-bg: #0d1117;
    }
  }
  .card,
  .panel {
    padding: var(--c-gap);
    color: var(--c-text);
  }
  .card.tone-ok:hover { border-left: 4px  solid  green }
  ```

- `close.css`: the two lines `a { color: red; }` and `}`.

Catch failures with `pytest.raises(kind_css.AssetError)` and compare
`str(excinfo.value)` exactly where a criterion gives the message.
Compare results with `==` against the exact values given.

All are `kind: generated-test`, calling the module's functions on
stylesheets a test writes under `tmp_path`.
