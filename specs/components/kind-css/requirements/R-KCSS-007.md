# R-KCSS-007

**R-KCSS-007** — `strength_sites(asset_file)` MUST return one
`StrengthSite` (`interface/data/StrengthSite.md`) per declaration in
text order, every rule's, `@media` blocks' included, a declaration being
non-empty after stripping and holding a `:`. A file with no
declarations, or whose layout is invalid, gives `[]`.
