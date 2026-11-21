# R-ASSEMBLE-016

**R-ASSEMBLE-016** — Asset kinds (`D343`,
  `specs/architecture/asset-kinds.md`). Wherever this component includes
  a component's `interface/` content, the documents `R-ASSEMBLE-002`
  and `R-ASSEMBLE-014` already name are followed, after its
  `interface/guarantees/` documents and before any `Implements:`
  document, by each `interface/assets/*.md` file in sorted file-name
  order, its text read from disk and stripped.

  The target's declared kinds are, for each string in its
  `component.md` frontmatter `assets` (read through `load_corpus`'s
  `Component`, `R-ASSEMBLE-012`), the text before its first `:`,
  de-duplicated and sorted; none when the key is absent. A kind's
  adapter is `<repo_root>/gen/kind-<kind>/kind_<module>.py`, or, when that
  file does not exist, the same path under the tool root
  (`R-ASSEMBLE-015`), loaded by path afresh on each call. With neither,
  both functions raise `PreconditionFailure` with the message
  `unknown asset kind: <kind>`. Its `guidance()` is called once per
  kind and returns `{"generator": str, "test_author": str}`; each text
  is used stripped. No definition document is read.

  `assemble` MUST append to `SpecBundle.interface`, after every document
  `R-ASSEMBLE-014` appends, for each declared kind in order,
  `"\n\n## Asset kind: " + kind + "\n\n" + generator`. `assemble_criterion`
  MUST append to `CriterionBundle.testing`, after any `Uses:` documents,
  for each, `"\n## Asset kind: " + kind + "\n\n" + test_author`.
  Neither text appears in the other bundle.
