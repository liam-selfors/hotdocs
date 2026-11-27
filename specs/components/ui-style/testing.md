Tests import the module as `import ui_style`. They read the stylesheet
only through the `asset_runner` fixture,
`run = asset_runner("static/style.css")`, and through `ui_style`'s own
functions; they never parse the `.css` text themselves.

A page for the browser: write `tmp_path / "p.html"` as exactly
`'<!doctype html><html><head>' + ui_style.style_element() +
'</head><body><ul><li class="node tone-fail">x</li></ul>' +
'<a href="#">y</a></body></html>'`, then
`page = browser.open(tmp_path / "p.html")` (or with
`color_scheme="dark"`), and read computed values with
`page.find(css=...).style(<property>)`.
