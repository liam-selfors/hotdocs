# hotdocs-criterion: sha256:5de6d30dc96821dfa22af5538a40be29e28c30800c18f6e32101d2c376630cc2
import pytest

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_dict(site):
    if isinstance(site, dict):
        return dict(site)
    return {
        "description": field(site, "description"),
        "offset": field(site, "offset"),
        "token": field(site, "token"),
        "swap": field(site, "swap"),
    }


ORIGINAL = b"export function f(a, b) {\r\n  return a - b < 0;\r\n}\r\n"
EXPECTED = b"export function f(a, b) {\r\n  return a - b >= 0;\r\n}\r\n"


def test_apply_site_replaces_one_token_and_keeps_crlf(tmp_path):
    path = tmp_path / "a.js"
    path.write_bytes(ORIGINAL)

    sites = kind_javascript.strength_sites(path)
    descriptions = [field(s, "description") for s in sites]
    assert descriptions == ["2: - -> +", "2: < -> >="]

    # Listing sites must not change the file.
    assert path.read_bytes() == ORIGINAL

    result = kind_javascript.apply_site(path, sites[1])
    assert result is None
    assert path.read_bytes() == EXPECTED


def test_apply_site_with_mismatched_token_raises_and_leaves_file(tmp_path):
    path = tmp_path / "a.js"
    path.write_bytes(ORIGINAL)

    sites = kind_javascript.strength_sites(path)
    descriptions = [field(s, "description") for s in sites]
    assert descriptions == ["2: - -> +", "2: < -> >="]

    bad = as_dict(sites[0])
    bad["token"] = "*"

    with pytest.raises(ValueError):
        kind_javascript.apply_site(path, bad)

    assert path.read_bytes() == ORIGINAL