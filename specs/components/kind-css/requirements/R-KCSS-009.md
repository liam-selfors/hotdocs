# R-KCSS-009

**R-KCSS-009** — `guidance()` MUST return a new dict with exactly the
keys `"generator"` and `"test_author"`, whose values are exactly the
text of `specs/architecture/asset-kind-css.md`'s `## Generator guidance`
and `## Test author guidance` sections: the lines after the section's
heading line up to the next line starting `## ` or the end of the
document, joined with `"\n"` and stripped. The module holds the texts
itself and reads no file to produce them.
