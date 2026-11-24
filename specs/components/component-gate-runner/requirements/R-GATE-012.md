# R-GATE-012

**R-GATE-012** — `run_component_gates` MUST take `reauthor`, a list of
  criterion ids or `None` (`D370`). On a non-sealed component whose
  provenance check is not a short-circuiting hit
  (`interface/data/ComponentPipelineResult.md`), for any `reason`, before
  any other call after it, it deletes
  `<repo_root>/verification/<slug>/generated-test/test_<id>.py` (`<id>`
  lowercased, `-` as `_`) for each id whose file exists, so the
  verification that follows (`R-GATE-011`'s too) authors them afresh. On a short-circuiting hit, or for a sealed component,
  nothing is deleted.

  `main` MUST take `--reauthor` as `specs/architecture/generate-cli.md`
  says, passing its ids as that list, `None` when not given, and check it
  after every other usage check. Each usage error is exit `2`, with no
  dependency called:
  - an empty value or an empty entry: `--reauthor needs criterion ids`;
  - a sealed component (`sealed: true` in its `component.md`
    frontmatter): `--reauthor does not apply to sealed <component-id>`;
  - an id not matching `AC-[A-Za-z0-9-]+`, or with no file
    `specs/components/<slug>/acceptance/<id>.md` holding a line that,
    stripped, is `Kind: generated-test`:
    `<id> is not a generated-test criterion of <component-id>`.
