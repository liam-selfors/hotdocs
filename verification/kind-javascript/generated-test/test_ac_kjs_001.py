# hotdocs-criterion: sha256:d9b8a26c3111846ce76313275f3e3a05085dd10c335fa2fa79e4ef0dce718cb3
import inspect

import pytest

import kind_javascript


def test_kind_constant():
    assert kind_javascript.KIND == "javascript"
    assert isinstance(kind_javascript.KIND, str)


def test_gate_version_constant():
    assert kind_javascript.GATE_VERSION == "kind-javascript@1.0.0"
    assert isinstance(kind_javascript.GATE_VERSION, str)


def test_asset_error_is_exception_class():
    assert inspect.isclass(kind_javascript.AssetError)
    assert issubclass(kind_javascript.AssetError, Exception) is True


def test_asset_error_message():
    err = kind_javascript.AssetError("x")
    assert str(err) == "x"
    assert isinstance(err, Exception)


def test_asset_error_can_be_raised_and_caught():
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        raise kind_javascript.AssetError("x")
    assert str(excinfo.value) == "x"