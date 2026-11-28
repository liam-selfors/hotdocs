# hotdocs-criterion: sha256:e9699ebb5ec39de669a622912a151cc7862dc4e723bc3a7fa4822e73ccad41a0
import ui_style


PAGE_HTML_PREFIX = '<!doctype html><html><head>'
PAGE_HTML_BODY = (
    '</head><body><ul><li class="node tone-fail">x</li></ul>'
    + '<a href="#">y</a></body></html>'
)


def write_page(tmp_path):
    path = tmp_path / "p.html"
    path.write_text(
        PAGE_HTML_PREFIX + ui_style.style_element() + PAGE_HTML_BODY,
        encoding="utf-8",
    )
    return path


def test_ac_style_005_light_computed_styles(browser, tmp_path):
    path = write_page(tmp_path)
    page = browser.open(path)

    li = page.find(css="li.node")
    assert li.style("border-left-color") == "rgb(209, 36, 47)"
    assert li.style("border-top-color") == "rgb(209, 217, 224)"
    assert li.style("border-left-width") == "4px"

    body = page.find(css="body")
    assert body.style("background-color") == "rgb(255, 255, 255)"

    assert page.console_errors() == []


def test_ac_style_005_dark_computed_styles(browser, tmp_path):
    path = write_page(tmp_path)
    page = browser.open(path, color_scheme="dark")

    li = page.find(css="li.node")
    assert li.style("border-left-color") == "rgb(248, 81, 73)"

    body = page.find(css="body")
    assert body.style("background-color") == "rgb(13, 17, 23)"