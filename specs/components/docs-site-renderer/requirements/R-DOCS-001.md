# R-DOCS-001

**R-DOCS-001** — MUST render an interactive, clickable, searchable DAG
  from `corpus-graph.json`'s `nodes`/`edges` — one node per product
  capability, component, and var; edges for `depends_on`, `realizes`, and
  `uses_var` (`notes/initial-ideas.md`'s own D9).

  `index.html` holds a `<input id="search" type="search">`, an empty
  `<svg id="dag"></svg>`, `<ul id="nodes">` with one
  `<li class="node" data-id=... data-type=...>` per node, sorted by id,
  each linking to its detail page, and `<ul id="edges">` with one
  `<li class="edge" data-from=... data-to=... data-kind=...>` per edge,
  in input order. Layout and search happen in the browser, in the
  declared asset `static/app.js` (`interface/assets/app.js.md`,
  `R-DOCS-008`, `R-DOCS-009`, `D343`); the Python code computes no
  layout and holds no JavaScript of its own. `render_docs_site` reads
  the asset as UTF-8 from `Path(__file__).parent.parent / "static" /
  "app.js"` (`__file__` being `docs_site_renderer/__init__.py`, so the
  asset is `gen/docs-site-renderer/static/app.js`) and writes it into
  `index.html` exactly once, unchanged, as the element
  `<script type="module">` + its text + `\ninit(document);\n` +
  `</script>`, the page's only `<script` element. Detail and dashboard
  pages carry no script. The asset contains no `</script`.

  The pages are `out_dir/index.html`, `out_dir/dashboard.html` and one
  detail page per node, `out_dir/nodes/<node id>.html`. Every page
  written, `index.html`, each detail page and the dashboard,
  has `ui_style.style_element()` once inside `<head>` as its only CSS,
  loaded as `specs/architecture/visual-style.md` "Pages" states: no
  other `<style>` element, no `style="..."` attribute and no `<link`
  element.
