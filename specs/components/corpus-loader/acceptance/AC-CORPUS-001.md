# AC-CORPUS-001

Covers: R-CORPUS-001
Kind: generated-test

```gherkin
Given a repo_root holding specs/glossary.md with the entry line
  "- **Widget** — a part.", specs/components/foo/component.md with
  frontmatter id comp-foo, owners [team-a], sealed true and
  source_path legacy/foo/, then the body "# Foo", requirements/R-FOO-001.md,
  acceptance/AC-FOO-001.md, interface/library.md, interface/data/Thing.md,
  constraints.md and a README.md, plus specs/decisions/D200.md with id D200
When load_corpus(repo_root) runs
Then components["foo"].root.frontmatter is {"id": "comp-foo", "owners":
  ["team-a"], "sealed": True, "source_path": "legacy/foo/"} and its body
  begins at the line after the closing ---; requirements is keyed
  "R-FOO-001", acceptance "AC-FOO-001", interface_data "Thing"; each
  Doc's doc_type is as Corpus.md gives, every path is absolute and every
  rel_path relative; no Doc is made for README.md or the glossary;
  id_index holds comp-foo and D200; glossary_defs maps "widget" to the
  text after the bold header; glossary_files holds the glossary's
  absolute path
```
