# hotdocs-criterion: sha256:11f3444812bd3bbc60069f3abdf1a6a191ff71ff6490a4803fca38487d158691
import kind_javascript

import pytest


SOURCE = (
    "export function boom(m) { throw new Error('bad: ' + m); }\n"
    "export function plain() { throw 'plain text'; }\n"
    "export const notfn = 3;\n"
)


def make_runner(tmp_path):
    path = tmp_path / "m.js"
    path.write_text(SOURCE, encoding="utf-8")
    return kind_javascript.asset_runner(path)


def test_error_message_is_raised(tmp_path):
    run = make_runner(tmp_path)
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("boom", ["x"])
    assert str(excinfo.value) == "bad: x"


def test_thrown_non_error_value_is_stringified(tmp_path):
    run = make_runner(tmp_path)
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("plain", [])
    assert str(excinfo.value) == "plain text"


def test_missing_export(tmp_path):
    run = make_runner(tmp_path)
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("missing", [])
    assert str(excinfo.value) == "no export missing"


def test_export_not_a_function(tmp_path):
    run = make_runner(tmp_path)
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("notfn", [])
    assert str(excinfo.value) == "no export notfn"