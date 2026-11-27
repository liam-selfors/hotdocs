# hotdocs-criterion: sha256:b3c5a0bc3c95bc8ba9d44e9f568c3855e0ae3cf542d1fcde5c1c6b595e0e0171
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

CLOSE_CSS = "a { color: red; }\n" "}\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _as_dict(site):
    return {
        name: field(site, name)
        for name in ("description", "offset", "end", "property")
    }


def test_strength_sites_of_s_css(tmp_path):
    path = tmp_path / "s.css"
    path.write_text(S_CSS, encoding="utf-8")

    result = kind_css.strength_sites(path)

    expected = [
        {"description": "2: --c-text removed", "offset": 10, "end": 28, "property": "--c-text"},
        {"description": "3: --c-bg removed", "offset": 31, "end": 47, "property": "--c-bg"},
        {"description": "4: --c-gap removed", "offset": 50, "end": 63, "property": "--c-gap"},
        {"description": "8: --c-bg removed", "offset": 118, "end": 134, "property": "--c-bg"},
        {"description": "13: padding removed", "offset": 159, "end": 181, "property": "padding"},
        {"description": "14: color removed", "offset": 184, "end": 205, "property": "color"},
        {"description": "16: border-left removed", "offset": 230, "end": 261, "property": "border-left"},
    ]

    assert isinstance(result, list)
    assert [_as_dict(site) for site in result] == expected
    assert result == expected


def test_strength_sites_of_close_css_is_empty(tmp_path):
    path = tmp_path / "close.css"
    path.write_text(CLOSE_CSS, encoding="utf-8")

    result = kind_css.strength_sites(path)

    assert result == []