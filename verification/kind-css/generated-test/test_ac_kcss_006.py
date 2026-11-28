# hotdocs-criterion: sha256:0b557c97222dca5601bd3e947dd679c903a07af456d05484e3097df02d400cc1
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


def test_ac_kcss_006_asset_runner_tokens_rule_errors_and_reparse(tmp_path):
    path = tmp_path / "s.css"
    path.write_text(S_CSS, encoding="utf-8")

    run = kind_css.asset_runner(path)
    assert callable(run)

    assert run("tokens", []) == {
        "--c-text": "#1f2328",
        "--c-bg": "#ffffff",
        "--c-gap": "8px",
    }
    assert run("tokens", ["dark"]) == {"--c-bg": "#0d1117"}
    assert run("rule", [".card, .panel"]) == {
        "padding": "var(--c-gap)",
        "color": "var(--c-text)",
    }
    assert run("rule", [".card.tone-ok:hover"]) == {
        "border-left": "4px solid green"
    }

    with pytest.raises(kind_css.AssetError) as excinfo:
        run("rule", [".card"])
    assert str(excinfo.value) == "no rule .card"

    with pytest.raises(kind_css.AssetError) as excinfo:
        run("style", [])
    assert str(excinfo.value) == "no entry style"

    # The same run re-reads the file as it is at each call.
    path.write_text("a {\n  color: red;\n}\n", encoding="utf-8")
    assert run("rule", ["a"]) == {"color": "red"}

    path.write_text("}\n", encoding="utf-8")
    with pytest.raises(kind_css.AssetError) as excinfo:
        run("tokens", [])
    assert str(excinfo.value) == "invalid layout: parse error: line 1: unexpected }"