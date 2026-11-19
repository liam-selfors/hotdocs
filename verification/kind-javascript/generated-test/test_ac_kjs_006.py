# hotdocs-criterion: sha256:118fad7ee59409d5cbe80aa027499755c6b10f7d7df6d49f016872743d1d21a5
import shutil

import pytest

import kind_javascript


ASSET_TEXT = (
    "export function boom(m) { throw new Error('bad: ' + m); }\n"
    "export function plain() { throw 'plain text'; }\n"
    "export const notfn = 3;\n"
)


@pytest.fixture
def run(tmp_path):
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH")
    asset = tmp_path / "m.js"
    asset.write_text(ASSET_TEXT, encoding="utf-8")
    return kind_javascript.asset_runner(asset)


def _raised_message(run, entry, args):
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run(entry, args)
    return str(excinfo.value)


def test_thrown_error_message_is_raised(run):
    assert _raised_message(run, "boom", ["x"]) == "bad: x"


def test_thrown_non_error_value_is_raised_as_string(run):
    assert _raised_message(run, "plain", []) == "plain text"


def test_missing_export_raises_no_export(run):
    assert _raised_message(run, "missing", []) == "no export missing"


def test_non_function_export_raises_no_export(run):
    assert _raised_message(run, "notfn", []) == "no export notfn"


def test_asset_error_is_an_exception():
    assert issubclass(kind_javascript.AssetError, Exception)