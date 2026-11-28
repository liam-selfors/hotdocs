# R-KCSS-003

**R-KCSS-003** — `surface(asset_file)` MUST return `{"names": names}`:
the sorted list, each name once, of every custom property declared in
a top-level rule whose prelude is exactly `:root` after stripping, and
of every class in any rule's prelude, `@media` blocks included, a class
being `.` followed by `[A-Za-z_-][A-Za-z0-9_-]*`, written with its `.`.
A file whose layout is invalid gives `{"names": []}`; `surface` never
raises.
