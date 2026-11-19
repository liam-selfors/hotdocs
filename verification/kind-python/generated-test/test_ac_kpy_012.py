# hotdocs-criterion: sha256:4298aacdf8f9f173d0d444bfe6d861ec6939c0953a3920427cd80882753a67b1
import kind_python


def test_guidance_returns_new_empty_dict_each_call():
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