# hotdocs-criterion: sha256:f4a42e59baa05dfc5264ba9c8a5971edc176cd85778010c8e9d97fc6136ef559
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

CLOSE_CSS = "a { color: red; }\n}\n"


def test_surface_of_s_css(tmp_path):
    path = tmp_path / "s.css"
    path.write_text(S_CSS, encoding="utf-8")
    result = kind_css.surface(path)
    assert result == {
        "names": ["--c-bg", "--c-gap", "--c-text", ".card", ".panel", ".tone-ok"]
    }


def test_surface_of_close_css(tmp_path):
    path = tmp_path / "close.css"
    path.write_text(CLOSE_CSS, encoding="utf-8")
    result = kind_css.surface(path)
    assert result == {"names": []}