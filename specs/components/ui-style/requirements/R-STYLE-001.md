# R-STYLE-001

**R-STYLE-001** — `stylesheet()` MUST return the text of
`Path(__file__).parent / "static" / "style.css"` read as UTF-8 at each
call, unchanged, and `style_element()` MUST return exactly
`"<style>\n" + stylesheet() + "</style>"`. The module imports nothing
outside Python's standard library, makes no model call and reads no
other file. The asset follows `specs/architecture/asset-kind-css.md`'s
generator guidance and contains no `</style`.
