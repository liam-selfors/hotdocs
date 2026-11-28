# R-PACKET-014

**R-PACKET-014** — The packet's `screenshots` MUST map each id in
  `regenerated_components`, in that order, to the sorted list of the
  paths, relative to `repo_root` and written with `/`, of every `*.png`
  at any depth under `<repo_root>/.hotdocs/screenshots/<slug>/` (where
  verification leaves a browser criterion's pages, `D390`), `[]` when
  there is none or no such directory. The markdown rendering MUST have a
  `## Screenshots` section directly after `## Verification Results`
  holding, per file, the flat line
  `- <component-id>: ![<path after the component's directory>](<path>)`,
  or the one line `_No screenshots._` when every list is empty, then the
  line `Screenshots are local files under .hotdocs/ (not committed); attach them to the PR to show them there.`
