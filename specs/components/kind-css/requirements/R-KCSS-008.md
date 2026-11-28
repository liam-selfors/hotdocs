# R-KCSS-008

**R-KCSS-008** — `apply_site(asset_file, site)` MUST check that the
file's text from `site["offset"]` starts with `site["property"]` (else
raise `ValueError` and leave the file unchanged), then write back,
UTF-8 with no newline translation,
`text[:site["offset"]] + text[site["end"]:]`: that one declaration
removed, every other character unchanged.
