# hotdocs-criterion: sha256:add77eddafe801f6118aac96952b62caad3b14be13de6df0f4e2dd5fdcd469a4
import pytest

import kind_javascript


SOURCE = (
    "export function boom(m) { throw new Error('bad: ' + m); }\n"
    "export function plain() { throw 'plain text'; }\n"
    "export const notfn = 3;\n"
)


@pytest.fixture
def run(tmp_path):
    path = tmp_path / "m.js"
    path.write_text(SOURCE, encoding="utf-8")
    return kind_javascript.asset_runner(path)


def test_thrown_error_message_becomes_asset_error(run):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("boom", ["x"])
    assert str(excinfo.value) == "bad: x"


def test_thrown_non_error_value_as_string(run):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("plain", [])
    assert str(excinfo.value) == "plain text"


def test_missing_export(run):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("missing", [])
    assert str(excinfo.value) == "no export missing"


def test_export_not_a_function(run):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run("notfn", [])
    assert str(excinfo.value) == "no export notfn"