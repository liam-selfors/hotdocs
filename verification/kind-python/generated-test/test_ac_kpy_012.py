# hotdocs-criterion: sha256:7016c944aa16d9165b2eeec932cbd523b9db869f85c87f64e9450134a7c369c2
import kind_python


def test_ac_kpy_012_guidance_returns_new_empty_dict_each_call(monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    first = kind_python.guidance()
    second = kind_python.guidance()

    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert first == {"generator": "", "test_author": ""}
    assert second == {"generator": "", "test_author": ""}

    first["extra"] = "added"

    assert "extra" not in second
    assert second == {"generator": "", "test_author": ""}

    third = kind_python.guidance()
    assert third == {"generator": "", "test_author": ""}