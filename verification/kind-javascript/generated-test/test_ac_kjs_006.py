# hotdocs-criterion: sha256:df92bc20589cd24f86884aee8bc0e78baddf3644610b557af124e8aeb0f8bc8d
import pytest

import kind_javascript


ASSET_TEXT = (
    "export function boom(m) { throw new Error('bad: ' + m); }\n"
    "export function plain() { throw 'plain text'; }\n"
    "export const notfn = 3;\n"
)


@pytest.fixture
def run(tmp_path):
    path = tmp_path / "m.js"
    path.write_text(ASSET_TEXT, encoding="utf-8")
    return kind_javascript.asset_runner(path)


def test_thrown_error_message_is_raised(run):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("boom", ["x"])
    assert str(excinfo.value) == "bad: x"


def test_thrown_non_error_value_is_raised_as_string(run):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("plain", [])
    assert str(excinfo.value) == "plain text"


def test_missing_export_raises_no_export(run):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("missing", [])
    assert str(excinfo.value) == "no export missing"


def test_non_function_export_raises_no_export(run):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("notfn", [])
    assert str(excinfo.value) == "no export notfn"