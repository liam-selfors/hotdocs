# R-KCSS-001

**R-KCSS-001** — The module MUST define `KIND = "css"`,
`GATE_VERSION = "kind-css@1.0.0"` and `class AssetError(Exception)`,
the one exception type `asset_runner`'s callable raises. It MUST make no
model call, start no process, open no network connection and import
nothing from `hotdocs` or from any other component.
