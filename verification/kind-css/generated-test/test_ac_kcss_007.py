# hotdocs-criterion: sha256:51d609ffbd436e8993ebc0c84b78b9ba35ecce6a703d3f31649387df5c72bf5d
import pytest

import kind_css


S_CSS = (
    ":root {\n"
    "  --c-text: #1f2328;\n"
    "  --c-bg: #ffffff;\n"
    "  --c-gap: 8px;\n"
    "}\n"
    "@media (prefers-color-scheme: dark) {\n"
    "  :root {\n"
    "    --c-bg: #0d1117;\n"
    "  }\n"
    "}\n"
    ".card,\n"
    ".panel {\n"
    "  padding: var(--c-gap);\n"
    "  color: var(--c-text);\n"
    "}\n"
    ".card.tone-ok:hover { border-left: 4px  solid  green }\n"
)


@pytest.fixture
def run(tmp_path):
    path = tmp_path / "s.css"
    path.write_text(S_CSS, encoding="utf-8")
    return kind_css.asset_runner(path)


def test_contrast_light(run):
    result = run("contrast", ["--c-text", "--c-bg"])
    assert isinstance(result, float)
    assert result == 15.8


def test_contrast_order_does_not_matter(run):
    result = run("contrast", ["--c-bg", "--c-text"])
    assert isinstance(result, float)
    assert result == 15.8


def test_contrast_dark(run):
    result = run("contrast", ["--c-text", "--c-bg", "dark"])
    assert isinstance(result, float)
    assert result == 1.2


def test_contrast_missing_token(run):
    with pytest.raises(kind_css.AssetError) as excinfo:
        run("contrast", ["--c-x", "--c-bg"])
    assert str(excinfo.value) == "no token --c-x"


def test_contrast_not_a_colour(run):
    with pytest.raises(kind_css.AssetError) as excinfo:
        run("contrast", ["--c-gap", "--c-bg"])
    assert str(excinfo.value) == "not a #rrggbb colour: --c-gap"