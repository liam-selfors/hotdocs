# AC-CORPUS-003

Covers: R-CORPUS-001
Kind: generated-test

```gherkin
Given a repo_root holding specs/product/P-X.md, specs/architecture/a.md,
  specs/vars/v.md and a decision record under specs/decisions/, each with
  a frontmatter id,
  specs/components/foo/interface/guarantees/G-FOO-001.md,
  specs/components/foo/interface/cli.md, and a component.md whose
  frontmatter lines are tags: [], flag: false, title: "Quoted", and
  depends_on: [comp-a, comp-b]
And a README.md in each of specs/product/, specs/architecture/,
  specs/vars/ and specs/decisions/
And a glossary whose entry "- **Gadget** — a tool" continues on a
  second line "used for tests." before the next "- **Widget** — a part."
When load_corpus(repo_root) runs
Then those docs have doc_type product, architecture, var, decision,
  component-interface-guarantee and component-interface-cli;
  interface_guarantees is keyed "G-FOO-001"; the frontmatter values are
  [], False, "Quoted" and ["comp-a", "comp-b"]; id_index holds the four
  frontmatter ids; and glossary_defs["gadget"] holds both lines' text
  and glossary_defs["widget"] exists; no Doc is made for any
  README.md
```
