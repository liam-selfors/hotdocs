# hotdocs-criterion: sha256:8abc7812da7eb42c755d6a54a3b71412f4015bb1f540973d71e33786f86924e7
import kind_javascript


TEST_AUTHOR_GUIDANCE = "\n".join([
    'Call the asset only through the `asset_runner` fixture:',
    '`run = asset_runner("<declared path>")`, then `run("<export>", [args])`,',
    'and compare the returned JSON with exact expected values. Every argument',
    'is plain JSON (dicts, lists, strings, numbers, booleans, `None`). Never',
    'start `node` yourself or search the `.js` file\'s text for words: a test',
    'that passes because a word is present checks nothing. Reading the file',
    'is allowed only to compare its whole text with something that must',
    'contain it verbatim, such as a page that inlines it. An',
    'export that takes a DOM object, such as `init(document)`, is not called',
    'by tests. Catch failures as `pytest.raises(Exception, match=...)` on the',
    'thrown message; the exception type is the adapter\'s.',
])

GENERATOR_GUIDANCE = "\n".join([
    'Write the asset as an ES module of pure functions over JSON values,',
    'each exported with `export function <name>(...)`, plus at most one',
    'export `init(document)` that only wires browser events to those',
    'functions: `init` contains no comparison, logical or arithmetic',
    'operator, no `true` or `false` and no condition, so every decision, and',
    'every mutation site, is in a pure export that tests call. No imports, no network, no `eval`, no globals beyond the',
    'module\'s own, and no regular expression literals (write',
    '`new RegExp("...")`), which the strength check\'s scan does not read.',
    'The text `</script` appears nowhere in the file, so a page can inline it.',
    'A page using the asset inlines its text in',
    '`<script type="module">` followed by `init(document);`.',
])


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_kjs_014_guidance_returns_exact_texts_as_new_dicts():
    expected = {"generator": GENERATOR_GUIDANCE, "test_author": TEST_AUTHOR_GUIDANCE}

    first = kind_javascript.guidance()
    second = kind_javascript.guidance()

    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert set(first.keys()) == {"generator", "test_author"}
    assert set(second.keys()) == {"generator", "test_author"}
    assert field(first, "generator") == GENERATOR_GUIDANCE
    assert field(first, "test_author") == TEST_AUTHOR_GUIDANCE
    assert first == expected
    assert second == expected

    first["generator"] = "changed"

    assert field(second, "generator") == GENERATOR_GUIDANCE
    assert second == expected

    third = kind_javascript.guidance()
    assert third == expected