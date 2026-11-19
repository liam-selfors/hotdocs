# R-SCAFFOLD-007

**R-SCAFFOLD-007** — `new_kind(repo_root, kind, title=None, owners=None,
  realizes=None)` MUST write a new asset kind's three parts and return
  their paths in this order: the definition
  `<repo_root>/specs/architecture/asset-kind-<kind>.md`, creating
  `specs/architecture/` if absent; the adapter's component directory
  `<repo_root>/specs/components/kind-<kind>/` (`R-SCAFFOLD-008`); and a
  draft decision record, exactly as
  `new_decision(repo_root, "Asset kind <kind>", owners=owners)` writes
  it. `title` defaults to `kind`, and `<owners>` is written as
  `new_decision` writes it (`[unassigned]` by default). The definition
  MUST be exactly these lines, each ending in a newline:

  ```
  ---
  id: arch-asset-kind-<kind>
  title: Asset kind <title>
  status: draft
  owners: [<owners>]
  depends_on: []
  ---

  # Asset kind `<kind>`

  TODO: say what the asset is and who consumes it; `comp-kind-<kind>` is its adapter.

  ## Layout

  TODO: state what the file at the declared path must be, and the exact message `layout_errors` returns for each way it can be wrong.

  ## Environment

  TODO: list each program the kind needs with its minimum version and the command that prints it, any lockfile under `environments/<kind>/`, and `provision`'s exact failure reasons.

  ## Surface

  TODO: state what a consumer may rely on, extractable by code without judgement, and its notation in the asset's interface file.

  ## Running criteria

  TODO: state what `asset_runner` takes and returns, with one example call and its JSON result.

  ## Strength check

  TODO: write this section first: choose mutation, perturbation or evaluation, and list every site, so that each concrete wrong version of an asset is caught by at least one.

  ## Test author guidance

  TODO: state exactly the text `guidance()["test_author"]` returns: how a test builds fixtures and calls `asset_runner`, and what it must not do, never a requirement restated.

  ## Generator guidance

  TODO: state exactly the text `guidance()["generator"]` returns: the conventions the asset must follow, never test mechanics.
  ```

  It MUST raise `ValueError` when `kind` does not match `^[a-z][a-z0-9]*$`
  (no hyphen: asset-kinds.md's Lookup names the adapter
  `kind_<kind>.py`, which differs from a hyphenated kind's module name)
  or is `python`, and
  `FileExistsError` when the definition or the component directory
  already exists, writing nothing, the decision record included, in any
  case.
