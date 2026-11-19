# hotdocs-criterion: sha256:6082275b1693fd37b5ba4e847268e1341fd91d670930029d2eaba7cdf21308bf
import inspect

import kind_javascript


def test_kind_constant():
    assert kind_javascript.KIND == "javascript"


def test_gate_version_constant():
    assert kind_javascript.GATE_VERSION == "kind-javascript@1.0.0"


def test_asset_error_is_exception_class():
    AssetError = kind_javascript.AssetError
    assert inspect.isclass(AssetError)
    assert issubclass(AssetError, Exception) is True


def test_asset_error_str_is_message():
    err = kind_javascript.AssetError("x")
    assert str(err) == "x"
    assert isinstance(err, Exception)