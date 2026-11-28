# hotdocs-criterion: sha256:d35413ea1525e4899d1ffbdfa5fa326fd53aac868dc70eddcd38ab2f0f537dbd
import kind_python


def test_guidance_returns_new_exact_dict_each_call(monkeypatch):
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

    second["other"] = "x"
    assert "other" not in first
    assert first == {"generator": "", "test_author": "", "extra": "added"}