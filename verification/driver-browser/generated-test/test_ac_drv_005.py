# hotdocs-criterion: sha256:526b6d68df31e95d256fba6fad3fef6301ec829c50d226977afc0c2c8f4d522b
import driver_browser


START = "Drive pages only through the `browser` fixture."
END = "`pytest.raises(Exception, match=...)` on the message."


def test_guidance_returns_only_test_author_key():
    result = driver_browser.guidance()
    assert isinstance(result, dict)
    assert list(result.keys()) == ["test_author"]


def test_guidance_test_author_text_bounds():
    result = driver_browser.guidance()
    text = result["test_author"]
    assert isinstance(text, str)
    assert text.startswith(START), repr(text[:200])
    assert text.endswith(END), repr(text[-200:])


def test_guidance_text_is_stripped():
    text = driver_browser.guidance()["test_author"]
    assert text == text.strip()


def test_guidance_is_stable_across_calls():
    assert driver_browser.guidance() == driver_browser.guidance()