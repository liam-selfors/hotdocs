# hotdocs-criterion: sha256:ebcce55cc9eedf9613374836709c6a68a91a662a58b33c5bc74a39b68e811cda
import ui_style


def _write_page(tmp_path):
    path = tmp_path / "p.html"
    path.write_text(
        '<!doctype html><html><head>'
        + ui_style.style_element()
        + '</head><body><ul><li class="node tone-fail">x</li></ul>'
        + '<a href="#">y</a></body></html>',
        encoding="utf-8",
    )
    return path


def test_ac_style_005_light(browser, tmp_path):
    path = _write_page(tmp_path)
    page = browser.open(path)
    li = page.find(css="li.node")
    assert li.style("border-left-color") == "rgb(209, 36, 47)"
    assert li.style("border-top-color") == "rgb(209, 217, 224)"
    assert li.style("border-left-width") == "4px"
    assert page.find(css="body").style("background-color") == "rgb(255, 255, 255)"
    assert page.console_errors() == []


def test_ac_style_005_dark(browser, tmp_path):
    path = _write_page(tmp_path)
    page = browser.open(path, color_scheme="dark")
    li = page.find(css="li.node")
    assert li.style("border-left-color") == "rgb(248, 81, 73)"
    assert page.find(css="body").style("background-color") == "rgb(13, 17, 23)"