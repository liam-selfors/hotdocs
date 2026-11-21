# hotdocs-criterion: sha256:924b62ad7a97ac0d7cfd1716bf74844aa25c2e31fed4c83e85fa8bf65095f1b3
from pathlib import Path

import kind_javascript


ASSET_TEXT = (
    "export function add(a, b) { return a + b; }\n"
    "export function nothing() {}\n"
    "export async function later(x) { return [x, {k: null}, true]; }\n"
    "export function noisy() { console.log('hi'); return 'ok'; }\n"
)


def _write_asset(tmp_path: Path) -> Path:
    path = tmp_path / "m.js"
    path.write_text(ASSET_TEXT, encoding="utf-8")
    return path


def test_ac_kjs_005_add_returns_decoded_values(tmp_path):
    path = _write_asset(tmp_path)
    run = kind_javascript.asset_runner(path)
    result = run("add", [1, 2])
    assert result == 3
    assert not isinstance(result, bool)
    assert run("add", ["a", "b"]) == "ab"


def test_ac_kjs_005_undefined_returns_none(tmp_path):
    path = _write_asset(tmp_path)
    run = kind_javascript.asset_runner(path)
    assert run("nothing", []) is None


def test_ac_kjs_005_async_result_is_awaited_and_decoded(tmp_path):
    path = _write_asset(tmp_path)
    run = kind_javascript.asset_runner(path)
    result = run("later", [5])
    assert result == [5, {"k": None}, True]
    assert isinstance(result, list)
    assert isinstance(result[1], dict)
    assert result[1]["k"] is None
    assert result[2] is True


def test_ac_kjs_005_earlier_printed_lines_are_ignored(tmp_path):
    path = _write_asset(tmp_path)
    run = kind_javascript.asset_runner(path)
    assert run("noisy", []) == "ok"


def test_ac_kjs_005_all_together(tmp_path):
    path = _write_asset(tmp_path)
    run = kind_javascript.asset_runner(path)
    assert run("add", [1, 2]) == 3 and run("add", ["a", "b"]) == "ab"
    assert run("nothing", []) is None
    assert run("later", [5]) == [5, {"k": None}, True]
    assert run("noisy", []) == "ok"