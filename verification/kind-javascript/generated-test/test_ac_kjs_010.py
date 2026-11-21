# hotdocs-criterion: sha256:d004da4af02b7c6a8ef892828670c15c982740aa6a0b0077ef036146b237afc2
import kind_javascript


LINES = [
    "const t = 'it\\'s < 1' + \"a \\\" > b\"; // c == d",
    "/* p && q */ const u = `x ${1 < 2}`;",
    "export const f = (a, b) => a === b || -a <= b;",
    "export function g(x) { return -x + x[0] - 1 >= true; }",
    "let n = 1 + 2; n++; n += 2; n = n >> 1 >>> 0 << 2;",
]

EXPECTED = [
    "3: === -> !==",
    "3: || -> &&",
    "3: <= -> >",
    "4: + -> -",
    "4: - -> +",
    "4: >= -> <",
    "4: true -> false",
    "5: + -> -",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_kjs_010_strength_sites_skip_strings_comments_unary_and_long_operators(tmp_path):
    text = "".join(line + "\n" for line in LINES)
    path = tmp_path / "a.js"
    path.write_text(text, encoding="utf-8")

    sites = kind_javascript.strength_sites(path)

    descriptions = [field(site, "description") for site in sites]
    assert descriptions == EXPECTED

    for site in sites:
        assert isinstance(site, dict)
        assert set(site.keys()) == {"description", "offset", "token", "swap"}
        offset = site["offset"]
        token = site["token"]
        assert isinstance(offset, int)
        assert text[offset:offset + len(token)] == token