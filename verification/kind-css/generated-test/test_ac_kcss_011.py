# hotdocs-criterion: sha256:3da9e66754420f30d670e06a129c0bdde4d315de1cc6587f82b185ed4489ebb8
import kind_css


GENERATOR_GUIDANCE = "\n".join([
    "Write plain CSS: rules of selectors and declarations, `:root` custom",
    "properties for every value a token names, and `@media` only one level",
    "deep. No `@import`, `@font-face` or other at-rule, no `url(`, no",
    "`expression(`, no `!important`, and no vendor hacks (a vendor-prefixed",
    "font-family keyword such as `-apple-system` is a plain value, not a",
    "hack). Write every",
    "colour as `#rrggbb` in lowercase. The text `</style` appears nowhere in",
    "the file, so a page can inline it.",
])

TEST_AUTHOR_GUIDANCE = "\n".join([
    "Call the asset only through the `asset_runner` fixture:",
    "`run = asset_runner(\"<declared path>\")`, then `run(\"rule\", [selector])`,",
    "`run(\"tokens\", [])`, `run(\"tokens\", [\"dark\"])` or",
    "`run(\"contrast\", [a, b])`, and compare the result with exact expected",
    "values. Never parse the `.css` file's text yourself or search it for",
    "words: a test that passes because a word is present checks nothing.",
    "Reading the file is allowed only to compare its whole text with",
    "something that must contain it verbatim, such as a page that inlines",
    "it, or to check that a text the layout forbids is absent. Catch failures as `pytest.raises(Exception, match=...)` on the",
    "message; the exception type is the adapter's.",
])


def test_guidance_returns_exact_section_texts_as_new_dicts():
    expected = {"generator": GENERATOR_GUIDANCE, "test_author": TEST_AUTHOR_GUIDANCE}

    first = kind_css.guidance()
    second = kind_css.guidance()

    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert set(first.keys()) == {"generator", "test_author"}
    assert set(second.keys()) == {"generator", "test_author"}
    assert first["generator"] == GENERATOR_GUIDANCE
    assert first["test_author"] == TEST_AUTHOR_GUIDANCE
    assert first == expected
    assert second == expected

    assert first is not second
    first["generator"] = "changed"
    assert second["generator"] == GENERATOR_GUIDANCE
    assert second == expected

    third = kind_css.guidance()
    assert third == expected