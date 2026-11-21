# R-KJS-001

**R-KJS-001** — The module MUST define `KIND = "javascript"`,
`GATE_VERSION = "kind-javascript@1.0.0"` and `class AssetError(Exception)`,
the one exception type `asset_runner`'s callable raises for a failure of
the asset or of Node. It MUST make no model call and no network access,
and MUST import nothing from `hotdocs` or from any other component.
