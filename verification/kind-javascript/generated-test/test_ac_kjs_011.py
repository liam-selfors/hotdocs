# hotdocs-criterion: sha256:c1b03fa5a7790262986dcc5764f56870f7bc7c0a575ff7de0ac9d1f34c6125dd
import pytest

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ORIGINAL = b"export function f(a, b) {\r\n  return a - b < 0;\r\n}\r\n"
MUTATED = b"export function f(a, b) {\r\n  return a - b >= 0;\r\n}\r\n"


def test_ac_kjs_011_apply_site_replaces_one_token_and_rejects_mismatch(tmp_path):
    path = tmp_path / "a.js"
    path.write_bytes(ORIGINAL)

    sites = kind_javascript.strength_sites(path)
    descriptions = [field(s, "description") for s in sites]
    assert descriptions == ["2: - -> +", "2: < -> >="]

    kind_javascript.apply_site(path, sites[1])
    assert path.read_bytes() == MUTATED

    before = path.read_bytes()
    bad_site = dict(sites[0], token="*")
    with pytest.raises(ValueError):
        kind_javascript.apply_site(path, bad_site)
    assert path.read_bytes() == before


def test_ac_kjs_011_mismatched_token_leaves_original_file_unchanged(tmp_path):
    path = tmp_path / "a.js"
    path.write_bytes(ORIGINAL)

    sites = kind_javascript.strength_sites(path)
    assert [field(s, "description") for s in sites] == ["2: - -> +", "2: < -> >="]

    bad_site = dict(sites[0], token="*")
    with pytest.raises(ValueError):
        kind_javascript.apply_site(path, bad_site)
    assert path.read_bytes() == ORIGINAL