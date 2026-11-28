# hotdocs-criterion: sha256:40843af6b69369b42a1b874fe3ef43ac2c21322586a670a5f01542f6d52924c2
import pytest

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_kjs_011_apply_site_replaces_one_token_and_rejects_mismatch(tmp_path):
    path = tmp_path / "a.js"
    original = b"export function f(a, b) {\r\n  return a - b < 0;\r\n}\r\n"
    path.write_bytes(original)

    sites = kind_javascript.strength_sites(path)
    descriptions = [field(site, "description") for site in sites]
    assert descriptions == ["2: - -> +", "2: < -> >="]

    # Reading sites must not change the file.
    assert path.read_bytes() == original

    result = kind_javascript.apply_site(path, sites[1])
    assert result is None

    expected = b"export function f(a, b) {\r\n  return a - b >= 0;\r\n}\r\n"
    assert path.read_bytes() == expected

    # A site whose token does not match the text at its offset is rejected
    # and the file is left unchanged.
    before = path.read_bytes()
    bad_site = dict(sites[0], token="*")
    with pytest.raises(ValueError):
        kind_javascript.apply_site(path, bad_site)
    assert path.read_bytes() == before

    # The same holds on a freshly written original file.
    path.write_bytes(original)
    with pytest.raises(ValueError):
        kind_javascript.apply_site(path, dict(sites[0], token="*"))
    assert path.read_bytes() == original