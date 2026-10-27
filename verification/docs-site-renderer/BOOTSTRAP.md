# Bootstrap Account: `docs-site-renderer`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D58`), in a single real `generate()`
call that passed verification on the first try.

A genuinely different kind of deliverable from every component built
before it — real static HTML/CSS/JS, not just Python logic — produced
cleanly: a DAG index page with client-side search, a per-node detail
page per component/capability/var, a corpus-health dashboard, and
correct handling of `sealed`/`pinned_overrides`/the `owners` exclusion
list (`R-DOCS-002`'s D9-minus-two-items rule). `render_docs_site`
itself never reads `verification/corpus-graph.json` (a separate
`load_corpus_graph` does that, wired together only in the CLI layer) —
a clean, correct reading of `R-DOCS-004`'s "pure function of the
graph" requirement.

One real gap found while building this component's own test suite
(`D71`): `R-DOCS-005` requires the rendered output never be committed,
and the CLI's own default output path is `dist/docs-site/` — but
`.gitignore` had no `dist/` entry at all, anywhere in this repo. A
careless `git add -A` after a local render could have committed it.
Fixed directly in `.gitignore`, not in this component's own code (it
already does the right thing; the gap was repo configuration, not
implementation).

Verified against all 6 `AC-DOCS-*` criteria for real, including a
real `git check-ignore` call confirming the default output path is
actually excluded now.
