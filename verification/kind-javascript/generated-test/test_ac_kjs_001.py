# hotdocs-criterion: sha256:1b4daa68635347bd2b595ea216a79620c27916145fd93a786aff7cf91186f92e
import inspect

import kind_javascript


def test_kind_constant():
    assert kind_javascript.KIND == "javascript"
    assert isinstance(kind_javascript.KIND, str)


def test_gate_version_constant():
    assert kind_javascript.GATE_VERSION == "kind-javascript@1.0.0"
    assert isinstance(kind_javascript.GATE_VERSION, str)


def test_asset_error_is_exception_class():
    error_type = kind_javascript.AssetError
    assert inspect.isclass(error_type)
    assert issubclass(error_type, Exception) is True


def test_asset_error_str_is_message():
    err = kind_javascript.AssetError("x")
    assert str(err) == "x"
    assert isinstance(err, Exception)