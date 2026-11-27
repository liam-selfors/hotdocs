# hotdocs-criterion: sha256:b6440c528df49f41012e6f2af27fc2aefb684a0c56e220598bdc522ce0a4cf1b
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


def _read(path):
    return path.read_bytes().decode("utf-8")


def test_ac_kcss_010_apply_site_removes_declaration_and_rejects_mismatch(tmp_path):
    path = tmp_path / "s.css"
    path.write_text(S_CSS, encoding="utf-8")

    # Sanity: the fixture is as the criterion assumes.
    assert S_CSS[118:134] == "--c-bg: #0d1117;"

    site = {
        "description": "8: --c-bg removed",
        "offset": 118,
        "end": 134,
        "property": "--c-bg",
    }
    result = kind_css.apply_site(path, site)
    assert result is None

    expected = S_CSS[:118] + S_CSS[134:]
    after = _read(path)
    assert after == expected
    assert after.split("\n")[7] == "    "

    before_bytes = path.read_bytes()
    bad_site = {"description": "x", "offset": 0, "end": 3, "property": "color"}
    with pytest.raises(ValueError):
        kind_css.apply_site(path, bad_site)
    assert path.read_bytes() == before_bytes
    assert _read(path) == expected