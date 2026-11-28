# hotdocs-criterion: sha256:7f84772b1e1b6280bf9e4a436391eab2e2b47244e37cdc7e4c9b086a6f98348e
import pytest

import kind_python


CALC_SOURCE = (
    "def add(a, b):\n    return a + b\n\n\n"
    "def nothing():\n    pass\n\n\n"
    "def pair(x):\n    print('noise', end='')\n    return [x, {'k': None}, True]\n"
)


def test_ac_kpy_004_asset_runner_runs_entries_at_call_time(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    code_dir = tmp_path / "calc"
    code_dir.mkdir(parents=True, exist_ok=True)
    calc_py = code_dir / "calc.py"
    calc_py.write_text(CALC_SOURCE, encoding="utf-8")

    run = kind_python.asset_runner(tmp_path / "calc")
    assert callable(run)

    assert run("add", [1, 2]) == 3
    assert run("add", ["a", "b"]) == "ab"
    assert run("nothing", []) is None
    assert run("pair", [5]) == [5, {"k": None}, True]

    calc_py.write_text("def add(a, b):\n    return 'new'\n", encoding="utf-8")
    assert run("add", [1, 2]) == "new"

    missing = tmp_path / "nope"
    monkeypatch.setenv("HOTDOCS_PYTHON", str(missing))

    with pytest.raises(kind_python.AssetError) as excinfo:
        run("add", [1, 2])
    assert str(excinfo.value) == "cannot start " + str(missing)

    assert kind_python.surface(tmp_path / "calc") == {"names": []}