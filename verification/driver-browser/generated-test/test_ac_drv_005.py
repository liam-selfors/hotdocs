# hotdocs-criterion: sha256:d822aad5d000e84ae63da29bcad363c2b436be1f8cb90838a319f6f4f94c50e1
import driver_browser


def test_ac_drv_005_guidance_returns_only_test_author_text():
    result = driver_browser.guidance()

    assert isinstance(result, dict)
    assert list(result.keys()) == ["test_author"]

    text = result["test_author"]
    assert isinstance(text, str)
    assert text.startswith("Drive pages only through the `browser` fixture.")
    assert text.endswith("`pytest.raises(Exception, match=...)` on the message.")