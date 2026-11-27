# hotdocs-criterion: sha256:f23a081c781615b9afb0410c6a36dad64e54836691a3dc3b435af90a8962020c
import inspect

import pytest

import kind_python


def test_ac_kpy_001_constants_and_asset_error(monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    assert kind_python.KIND == "python"
    assert isinstance(kind_python.KIND, str)

    assert kind_python.GATE_VERSION == "kind-python@1.0.0"
    assert isinstance(kind_python.GATE_VERSION, str)

    AssetError = kind_python.AssetError
    assert inspect.isclass(AssetError)
    assert issubclass(AssetError, Exception) is True

    err = AssetError("x")
    assert isinstance(err, Exception)
    assert str(err) == "x"

    with pytest.raises(kind_python.AssetError) as excinfo:
        raise kind_python.AssetError("x")
    assert str(excinfo.value) == "x"