# hotdocs-criterion: sha256:04ce5e4bfab9ff4f95732ddfb0796611fb599761d5cb79771627db499e530a7e
import pytest

import kind_python


CALC_SOURCE = (
    "def boom(m):\n    raise ValueError('bad: ' + m)\n\n\n"
    "def unjson():\n    return {1, 2}\n\n\n"
    "NOTFN = 3\n"
)


def _make_runner(tmp_path):
    code_dir = tmp_path / "calc"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / "calc.py").write_text(CALC_SOURCE, encoding="utf-8")
    return kind_python.asset_runner(code_dir)


def test_ac_kpy_005_boom_raises_exception_message(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    run = _make_runner(tmp_path)
    with pytest.raises(kind_python.AssetError) as excinfo:
        run("boom", ["x"])
    assert str(excinfo.value) == "bad: x"


def test_ac_kpy_005_unserializable_result(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    run = _make_runner(tmp_path)
    with pytest.raises(kind_python.AssetError) as excinfo:
        run("unjson", [])
    assert str(excinfo.value) == "Object of type set is not JSON serializable"


def test_ac_kpy_005_missing_entry(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    run = _make_runner(tmp_path)
    with pytest.raises(kind_python.AssetError) as excinfo:
        run("missing", [])
    assert str(excinfo.value) == "no entry missing"


def test_ac_kpy_005_non_callable_entry(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    run = _make_runner(tmp_path)
    with pytest.raises(kind_python.AssetError) as excinfo:
        run("NOTFN", [])
    assert str(excinfo.value) == "no entry NOTFN"