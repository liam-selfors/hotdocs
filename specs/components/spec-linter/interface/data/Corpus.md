# `Corpus`

`load_corpus(repo_root: Path) -> Corpus` is public: `spec-bundle-assembler`
and `impact-analyzer` read the corpus only through it. Dataclasses, fields
in this order:

- `Doc(path, rel_path, doc_id, frontmatter, body, doc_type, component=None, has_frontmatter=False)`
- `Component(name, root, requirements, interface_cli, interface_library, interface_data, interface_guarantees, acceptance, constraints)`
- `Corpus(repo_root, docs, components, id_index, glossary_defs, glossary_files, graph)`

Each `specs/**/*.md` file, by sorted path, is one `Doc` (`rel_path`
relative to `repo_root`), except `specs/glossary.md`, `README.md` files
and unlisted paths. `doc_type` under `specs/components/<c>/`:
`component.md` `component-root`, `requirements/R-*.md`
`component-requirement`, `interface/cli.md` and `library.md`
`component-interface-cli`/`-library`, `interface/data/*.md`
`component-interface-data`, `interface/guarantees/G-*.md`
`component-interface-guarantee`, `acceptance/AC-*.md`
`component-acceptance`, `constraints.md` `component-constraints`; files
directly in `specs/product|architecture|vars|decisions/` are `product`,
`architecture`, `var`, `decision`.

Frontmatter is a `---` block opening line 1: `[a, b]` a list of stripped
strings, `true`/`false` booleans, else an unquoted string. `body` is the
lines after the closing `---` joined by `\n`, or the whole text.
`doc_id` is the file stem for requirements, criteria and guarantees, else
frontmatter `id`.

`components` is keyed by directory name; `requirements`, `acceptance`,
`interface_guarantees` by `doc_id`; `interface_data` by stem. `id_index`
maps the `doc_id` of root, product, architecture, var and decision docs.
`glossary_defs` maps each lowercased `**term**` to its text;
`glossary_files` lists `specs/glossary*.md`. `graph` is a DuckDB
connection with `yaml` loaded and `graph-query-engine`'s views.
