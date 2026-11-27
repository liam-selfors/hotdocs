# hotdocs-criterion: sha256:cda31c4053a52d1f4501dcec8ec7af5b74cf8e5648d46eeeb2fd9d17b453f377
import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LINES = [
    "const t = 'it\\'s < 1' + \"a \\\" > b\"; // c == d",
    "/* p && q */ const u = `x ${1 < 2}`;",
    "export const f = (a, b) => a === b || -a <= b;",
    "export function g(x) { return -x + x[0] - 1 >= true; }",
    "let n = 1 + 2; n++; n += 2; n = n >> 1 >>> 0 << 2;",
]


def test_ac_kjs_010_strength_sites_scan(tmp_path):
    text = "".join(line + "\n" for line in LINES)
    path = tmp_path / "a.js"
    path.write_text(text, encoding="utf-8")

    sites = kind_javascript.strength_sites(path)

    descriptions = [field(site, "description") for site in sites]
    assert descriptions == [
        "3: === -> !==",
        "3: || -> &&",
        "3: <= -> >",
        "4: + -> -",
        "4: - -> +",
        "4: >= -> <",
        "4: true -> false",
        "5: + -> -",
    ]

    for site in sites:
        assert isinstance(site, dict)
        assert set(site.keys()) == {"description", "offset", "token", "swap"}
        offset = field(site, "offset")
        token = field(site, "token")
        assert isinstance(offset, int)
        assert text[offset:offset + len(token)] == token

    offsets = [field(site, "offset") for site in sites]
    assert offsets == sorted(offsets)