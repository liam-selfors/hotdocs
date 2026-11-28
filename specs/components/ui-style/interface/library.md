# Library

One module file, `ui_style.py`, never a package.

```
stylesheet() -> str
style_element() -> str
```

`stylesheet()` returns the declared asset `static/style.css`
(`interface/assets/style.css.md`), read as UTF-8 from
`Path(__file__).parent / "static" / "style.css"` at each call.
`style_element()` returns `"<style>\n" + stylesheet() + "</style>"`.

Implements: `specs/architecture/visual-style.md`
