# hotdocs-criterion: sha256:3571babe49a59f2653eedf79f38c228d09db8c880bc5d430fa64e27e26859491
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