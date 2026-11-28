# R-PROVCHECK-012

**R-PROVCHECK-012** — A miss whose reason would be `spec_bundle_hash
  differs` MUST instead have `reason` `hash formula differs` (`D394`)
  when git shows that no spec input of the component changed since its
  manifest was recorded and every other check would hit apart from the
  gate differences `R-PROVCHECK-013` allows (any `gate_versions` entry
  but `generator`) and an `environment differs` (`R-PROVCHECK-010`). The manifest was recorded at `C`, the last commit
  of `gen/<slug>/.provenance.json`
  (`git log -1 --format=%H -- <that path>`), and only when that file is
  tracked and unmodified in the working tree. The spec inputs are every
  file under `specs/components/<slug>/`, `specs/architecture/` and
  `specs/asset-kinds/`, `specs/glossary.md`, and every file under
  `specs/components/<dep-slug>/interface/` for each direct dependency;
  none changed when `git diff --quiet C -- <those paths>`, run at
  `repo_root`, exits `0`. Not a git repository, a manifest not tracked
  or modified, or any git command failing, keeps `spec_bundle_hash
  differs`. The same bytes can hash differently only when the hash's
  formula changed, so the committed code is re-verified, not
  regenerated.
