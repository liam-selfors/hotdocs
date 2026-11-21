# hotdocs-criterion: sha256:c3aacada325a5a4b655ac2a42f1e96a90714f1bd0b82251771b57b05283957d8
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
    calc_file = code_dir / "calc.py"
    calc_file.write_text(CALC_SOURCE, encoding="utf-8")

    run = kind_python.asset_runner(code_dir)
    assert callable(run)

    assert run("add", [1, 2]) == 3
    assert run("add", ["a", "b"]) == "ab"
    assert run("nothing", []) is None
    assert run("pair", [5]) == [5, {"k": None}, True]

    # The code is read at call time.
    calc_file.write_text("def add(a, b):\n    return 'new'\n", encoding="utf-8")
    assert run("add", [1, 2]) == "new"

    # An interpreter that cannot be started.
    nope = str(tmp_path / "nope")
    monkeypatch.setenv("HOTDOCS_PYTHON", nope)
    with pytest.raises(kind_python.AssetError) as excinfo:
        run("add", [1, 2])
    assert str(excinfo.value) == "cannot start " + nope

    assert kind_python.surface(code_dir) == {"names": []}