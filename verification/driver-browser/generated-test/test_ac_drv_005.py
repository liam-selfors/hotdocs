# hotdocs-criterion: sha256:8370c8e02f875c48f97df05614cb5e672b6abe1e504570065cf8cbb60953da0d
import driver_browser


START = "Drive pages only through the `browser` fixture."
END = "`pytest.raises(Exception, match=...)` on the message."


def test_guidance_returns_only_test_author_with_expected_text():
    result = driver_browser.guidance()

    assert isinstance(result, dict)
    assert list(result.keys()) == ["test_author"]

    text = result["test_author"]
    assert isinstance(text, str)
    assert text.startswith(START), repr(text[:120])
    assert text.endswith(END), repr(text[-120:])