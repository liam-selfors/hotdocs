# hotdocs-criterion: sha256:c90fb1c147c69ea5d4c9db754e9fe6fe0a047b32f122126d29d3075972d9e30d
import driver_browser


START = "Drive pages only through the `browser` fixture."
END = "`pytest.raises(Exception, match=...)` on the message."


def test_guidance_returns_only_test_author_with_documented_text():
    result = driver_browser.guidance()

    assert isinstance(result, dict)
    assert list(result.keys()) == ["test_author"]

    text = result["test_author"]
    assert isinstance(text, str)
    assert text.startswith(START)
    assert text.endswith(END)
    # The body is stripped: no surrounding whitespace.
    assert text == text.strip()


def test_guidance_is_stable_across_calls():
    first = driver_browser.guidance()
    second = driver_browser.guidance()
    assert first == second
    assert list(second.keys()) == ["test_author"]
    assert second["test_author"].startswith(START)
    assert second["test_author"].endswith(END)