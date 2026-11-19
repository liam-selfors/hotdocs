# R-KPY-008

**R-KPY-008** — `apply_site(asset_file, site)` MUST parse
`asset_file / site["file"]` as `R-KPY-007` does, take its sites in the
same order, and, when site number `site["index"]` exists and its
description equals `site["description"]`, apply that one change and
write the file back, UTF-8, as exactly `ast.unparse(<tree>)` with
nothing appended. Otherwise it raises `ValueError` and leaves the file
unchanged. Every other file is left as it is.
