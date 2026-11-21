# hotdocs-criterion: sha256:a87f095969ec821f9eaf4ce4fd8518e8b945658e3b617c36a5c44379223e38ab
import inspect

import kind_javascript


def test_kind_constant():
    assert kind_javascript.KIND == "javascript"
    assert isinstance(kind_javascript.KIND, str)


def test_gate_version_constant():
    assert kind_javascript.GATE_VERSION == "kind-javascript@1.0.0"
    assert isinstance(kind_javascript.GATE_VERSION, str)


def test_asset_error_is_exception_class():
    asset_error = kind_javascript.AssetError
    assert inspect.isclass(asset_error)
    assert issubclass(asset_error, Exception) is True


def test_asset_error_str_is_message():
    err = kind_javascript.AssetError("x")
    assert isinstance(err, Exception)
    assert str(err) == "x"