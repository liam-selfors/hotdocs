# R-SCAFFOLD-008

**R-SCAFFOLD-008** — `new_kind` MUST write the adapter's component
  directory exactly as `new_component(repo_root, "kind-<kind>",
  title="Kind <title>", owners=owners, realizes=realizes)` writes it,
  `.gitkeep` files included, and then add three files to it, each exactly
  these lines, each ending in a newline. `<module>` is `<kind>` with every
  `-` replaced by `_`, and `<KIND>` is `<kind>` uppercased (`yaml`
  gives `yaml` and `YAML`).

  `interface/library.md`:

  ~~~
  # Library

  One module file, `kind_<module>.py`, never a package.

  ```
  KIND: str           # "<kind>"
  GATE_VERSION: str   # "kind-<kind>@0.1.0"
  class AssetError(Exception)
  layout_errors(asset_file: Path) -> list[str]
  surface(asset_file: Path) -> dict
  provision(repo_root: Path) -> dict
  asset_runner(asset_file: Path) -> Callable[[str, list], object]
  strength_sites(asset_file: Path) -> list[dict]
  apply_site(asset_file: Path, site: dict) -> None
  guidance() -> dict
  ```

  Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-<kind>.md`
  ~~~

  `requirements/R-KIND-<KIND>-001.md`:

  ~~~
  # R-KIND-<KIND>-001

  **R-KIND-<KIND>-001** — TODO: `kind_<module>` MUST carry out `specs/architecture/asset-kind-<kind>.md`; replace this with one requirement per behaviour the definition states.
  ~~~

  `acceptance/AC-KIND-<KIND>-001.md`, the calibration pair to complete:

  ~~~
  # AC-KIND-<KIND>-001

  Covers: R-KIND-<KIND>-001
  Kind: generated-test

  ```gherkin
  Given TODO: a correct asset with a suite that checks it, and the same asset with a weak suite
  When each site strength_sites lists is applied alone with apply_site and each suite is run
  Then the correct suite kills at least the bar's share of the sites and the weak suite fewer
  ```
  ~~~
