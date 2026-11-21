# hotdocs-criterion: sha256:813b0bcaddc872b421ecf632a9714f1a11abe821edcf9c63dc7112b5cea4f4a5
import pytest

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE = b"export function f(a, b) {\r\n  return a - b < 0;\r\n}\r\n"
EXPECTED = b"export function f(a, b) {\r\n  return a - b >= 0;\r\n}\r\n"


def _sites(path):
    sites = kind_javascript.strength_sites(path)
    assert [field(s, "description") for s in sites] == ["2: - -> +", "2: < -> >="]
    return sites


def test_apply_site_replaces_exactly_one_token_preserving_crlf(tmp_path):
    path = tmp_path / "a.js"
    path.write_bytes(SOURCE)
    sites = _sites(path)

    result = kind_javascript.apply_site(path, sites[1])

    assert result is None
    assert path.read_bytes() == EXPECTED


def test_apply_site_mismatched_token_raises_and_leaves_file_unchanged(tmp_path):
    path = tmp_path / "a.js"
    path.write_bytes(SOURCE)
    sites = _sites(path)

    bad = dict(sites[0], token="*")
    with pytest.raises(ValueError):
        kind_javascript.apply_site(path, bad)

    assert path.read_bytes() == SOURCE


def test_mismatch_after_valid_apply_leaves_mutated_file_unchanged(tmp_path):
    path = tmp_path / "a.js"
    path.write_bytes(SOURCE)
    sites = _sites(path)

    kind_javascript.apply_site(path, sites[1])
    assert path.read_bytes() == EXPECTED

    before = path.read_bytes()
    with pytest.raises(ValueError):
        kind_javascript.apply_site(path, dict(sites[0], token="*"))
    assert path.read_bytes() == before