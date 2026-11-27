# hotdocs-criterion: sha256:f9af2c178d6a14156ccd929d21358604fd13d1f46fb4be11d61a05cdcf47a273
import pytest

import kind_python


SOURCE = (
    "def boom(m):\n    raise ValueError('bad: ' + m)\n\n\n"
    "def unjson():\n    return {1, 2}\n\n\n"
    "NOTFN = 3\n"
)


def _make_runner(tmp_path):
    code_dir = tmp_path / "calc"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / "calc.py").write_text(SOURCE, encoding="utf-8")
    return kind_python.asset_runner(code_dir)


def test_ac_kpy_005_failing_entries_raise_asset_error(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    run = _make_runner(tmp_path)

    with pytest.raises(kind_python.AssetError) as excinfo:
        run("boom", ["x"])
    assert str(excinfo.value) == "bad: x"

    with pytest.raises(kind_python.AssetError) as excinfo:
        run("unjson", [])
    assert str(excinfo.value) == "Object of type set is not JSON serializable"

    with pytest.raises(kind_python.AssetError) as excinfo:
        run("missing", [])
    assert str(excinfo.value) == "no entry missing"

    with pytest.raises(kind_python.AssetError) as excinfo:
        run("NOTFN", [])
    assert str(excinfo.value) == "no entry NOTFN"