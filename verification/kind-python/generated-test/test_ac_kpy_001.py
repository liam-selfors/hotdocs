# hotdocs-criterion: sha256:55b46d1582fca21a8051e84b964ad1dfc2c14343ff817f123d75334a9a63ba21
import inspect

import kind_python


def test_kind_constant():
    assert kind_python.KIND == "python"
    assert isinstance(kind_python.KIND, str)


def test_gate_version_constant():
    assert kind_python.GATE_VERSION == "kind-python@1.0.0"
    assert isinstance(kind_python.GATE_VERSION, str)


def test_asset_error_is_exception_class():
    assert inspect.isclass(kind_python.AssetError)
    assert issubclass(kind_python.AssetError, Exception)


def test_asset_error_str_is_message():
    err = kind_python.AssetError("x")
    assert str(err) == "x"
    assert isinstance(err, Exception)


def test_asset_error_can_be_raised_and_caught():
    try:
        raise kind_python.AssetError("x")
    except Exception as exc:
        assert isinstance(exc, kind_python.AssetError)
        assert str(exc) == "x"
    else:
        raise AssertionError("AssetError was not raised")