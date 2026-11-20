# hotdocs-criterion: sha256:5971e46d97e19b61ac01a3d4a9c8f8d04b793723c52529f2a8ae0114ba53efd1
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


def test_ac_kjs_010_strength_sites(tmp_path):
    text = "".join(line + "\n" for line in LINES)
    path = tmp_path / "a.js"
    path.write_bytes(text.encode("utf-8"))

    sites = kind_javascript.strength_sites(path)

    assert isinstance(sites, list)
    descriptions = [field(site, "description") for site in sites]
    assert descriptions == EXPECTED

    decoded = path.read_bytes().decode("utf-8")
    for site in sites:
        assert isinstance(site, dict)
        assert set(site.keys()) == {"description", "offset", "token", "swap"}
        offset = field(site, "offset")
        token = field(site, "token")
        assert isinstance(offset, int)
        assert isinstance(token, str)
        assert decoded[offset:offset + len(token)] == token