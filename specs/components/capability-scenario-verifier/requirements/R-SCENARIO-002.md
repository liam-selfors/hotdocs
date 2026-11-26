# R-SCENARIO-002

**R-SCENARIO-002** — The capability-intersection lookup
  (`R-SCENARIO-001`) MUST read `realizes` from each
  `specs/components/*/component.md` under `repo_root`: the frontmatter
  line starting `realizes:`, its items between `[` and `]` split on `,`
  and stripped. The capabilities to run are the distinct ids named by
  the components in the blast radius (`D376`). `realizes` is declared
  per component, never per capability (`D61`); no
  `specs/product/<name>.md` carries one.

  A capability's **realizing set** is every component whose `realizes`
  names it. A component's **code directory** is `gen/<slug>/`, or, when
  it is `sealed: true`, its frontmatter `source_path`, both under
  `repo_root`. Both are used by `R-SCENARIO-005` and `R-SCENARIO-006`.
