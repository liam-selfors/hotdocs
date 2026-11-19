# hotdocs-criterion: sha256:54007ef9b2be9d7f091792ec4ad6660b72fc44c115f0aa9b91abb94143bf025e
from pathlib import Path

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


def test_ac_kjs_010_strength_sites_scan(tmp_path):
    text = "".join(line + "\n" for line in LINES)
    asset = tmp_path / "a.js"
    asset.write_bytes(text.encode("utf-8"))

    sites = kind_javascript.strength_sites(Path(asset))

    assert isinstance(sites, list)
    descriptions = [field(site, "description") for site in sites]
    assert descriptions == EXPECTED

    for site in sites:
        if isinstance(site, dict):
            assert set(site.keys()) == {"description", "offset", "token", "swap"}
        else:
            for key in ("description", "offset", "token", "swap"):
                assert hasattr(site, key)
        offset = field(site, "offset")
        token = field(site, "token")
        assert isinstance(offset, int)
        assert isinstance(token, str)
        assert text[offset:offset + len(token)] == token