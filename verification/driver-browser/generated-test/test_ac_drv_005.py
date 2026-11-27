# hotdocs-criterion: sha256:30a0a81fcdce8f3dd412365e51dd86c0ebec63166d51bc134b2197dd5321f3c8
"""AC-DRV-005: guidance() returns the test author guidance text.

Covers: R-DRV-004
"""

import driver_browser


START = "Drive pages only through the `browser` fixture."
END = "`pytest.raises(Exception, match=...)` on the message."


def test_ac_drv_005_guidance_returns_only_test_author_text():
    result = driver_browser.guidance()

    assert isinstance(result, dict)
    assert list(result.keys()) == ["test_author"]

    text = result["test_author"]
    assert isinstance(text, str)
    assert text.startswith(START), repr(text[:200])
    assert text.endswith(END), repr(text[-200:])


def test_ac_drv_005_guidance_is_stable_across_calls():
    first = driver_browser.guidance()
    second = driver_browser.guidance()

    assert list(second.keys()) == ["test_author"]
    assert second["test_author"] == first["test_author"]
    assert second["test_author"].startswith(START)
    assert second["test_author"].endswith(END)