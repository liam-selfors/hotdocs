# hotdocs-criterion: sha256:ec05b88286d4eec1c421d3d57d9fc4a18899a4985c05aa7f3d89be9a55daad7f
from pathlib import Path

import pytest

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _node_ready(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(exist_ok=True)
    try:
        result = kind_javascript.provision(repo_root)
    except Exception:
        return False
    try:
        return bool(field(result, "ok"))
    except Exception:
        return False


def test_ac_kjs_004_surface_lists_sorted_export_names(tmp_path):
    if not _node_ready(tmp_path):
        pytest.skip("node >= 24 is not available; surface cannot import the module")

    asset = tmp_path / "m.js"
    asset.write_text(
        "export function beta(x) { return x; }\n"
        "export const alpha = 1;\n"
        "function hidden() { return 2; }\n"
        "export default 3;\n",
        encoding="utf-8",
    )

    result = kind_javascript.surface(asset)

    assert isinstance(result, dict)
    assert result == {"names": ["alpha", "beta", "default"]}


def test_ac_kjs_004_surface_of_unparseable_file_is_empty(tmp_path):
    asset = tmp_path / "bad.js"
    asset.write_text("export function f( {\n", encoding="utf-8")

    result = kind_javascript.surface(asset)

    assert isinstance(result, dict)
    assert result == {"names": []}