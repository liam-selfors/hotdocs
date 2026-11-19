# hotdocs-criterion: sha256:42ed2e87ab1134fb9c1497dcb81702a9af09469125836a8a3c2fdea359113395
import pytest

import kind_python


CALC_SOURCE = (
    "def boom(m):\n    raise ValueError('bad: ' + m)\n\n\n"
    "def unjson():\n    return {1, 2}\n\n\n"
    "NOTFN = 3\n"
)


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    code_dir = tmp_path / "calc"
    code_dir.mkdir()
    (code_dir / "calc.py").write_text(CALC_SOURCE)
    return kind_python.asset_runner(code_dir)


def test_raising_entry_gives_exception_message(run):
    with pytest.raises(kind_python.AssetError) as info:
        run("boom", ["x"])
    assert str(info.value) == "bad: x"


def test_unserializable_result_gives_json_error(run):
    with pytest.raises(kind_python.AssetError) as info:
        run("unjson", [])
    assert str(info.value) == "Object of type set is not JSON serializable"


def test_missing_entry(run):
    with pytest.raises(kind_python.AssetError) as info:
        run("missing", [])
    assert str(info.value) == "no entry missing"


def test_non_callable_entry(run):
    with pytest.raises(kind_python.AssetError) as info:
        run("NOTFN", [])
    assert str(info.value) == "no entry NOTFN"