# R-KJS-004

**R-KJS-004** — `provision(repo_root)` MUST run `node --version` as
`interface/library.md` "Finding node" states, write nothing, and return a
`ProvisionResult`, never raising:

- `node` not found, or the printed version's major part below 24:
  `ok` false, `reason` `javascript needs node >= 24`, `versions` `{}`.
- Output that, stripped and without one leading `v`, does not match
  `^\d+\.\d+\.\d+$`: `ok` false, `reason`
  `javascript environment: node --version printed <stripped output>`.
- A timeout or a non-zero exit: `ok` false, `reason`
  `javascript environment: node --version failed`.
- Otherwise `ok` true, `reason` `""`, `versions` `{"node": "<x.y.z>"}`.

`lockfile_sha256` is always `None`. `repo_root` is not read: the kind
has no packages and no environment directory.
