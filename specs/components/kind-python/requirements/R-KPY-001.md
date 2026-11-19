# R-KPY-001

**R-KPY-001** — The module MUST define `KIND = "python"`,
`GATE_VERSION = "kind-python@1.0.0"` and `class AssetError(Exception)`,
the one exception type `asset_runner`'s callable raises for a failure of
the code or of its process. It MUST make no model call and MUST import
nothing from `hotdocs` or from any other component (`D344`).
