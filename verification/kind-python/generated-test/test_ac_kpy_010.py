# hotdocs-criterion: sha256:7959ab42371c6350b9a975284059269ce1a2a042c9d41143f6e2c5014d2abb06
from pathlib import Path

import pytest

import kind_python


CALC_SRC = (
    '"""Calculator: a < b and True are prose here."""\n'
    "\n"
    "\n"
    "def check(a, b, xs):\n"
    "    flags = [a == b, a != b, a < b, a >= b, a > b, a <= b]\n"
    "    flags += [a is None, a is not None, a in xs, a not in xs]\n"
    "    return flags, 0 < a < 10\n"
    "\n"
    "\n"
    "def combine(a, b):\n"
    "    def inner(x):\n"
    "        return x * 2 / 4\n"
    "\n"
    "    return (a and b) or inner(a + b - 1) // 3 % 2, True, False\n"
)

PKG_SRC = (
    "def sign(n):\n"
    "    return -1 if n < 0 else 1\n"
)


def make_fixture(root):
    d = root / "calc"
    d.mkdir()
    (d / "calc.py").write_text(CALC_SRC, encoding="utf-8")
    (d / "pkg").mkdir()
    (d / "pkg" / "__init__.py").write_text(PKG_SRC, encoding="utf-8")
    return d


def test_apply_site_rewrites_one_file_and_rejects_mismatched_sites(tmp_path):
    # First scenario: sites[11] flips the outer `or` in combine.
    first = tmp_path / "first"
    first.mkdir()
    d = make_fixture(first)
    pkg_before = (d / "pkg" / "__init__.py").read_bytes()
    sites = kind_python.strength_sites(d)
    assert len(sites) > 20

    kind_python.apply_site(d, sites[11])

    expected_calc = (
        '"""Calculator: a < b and True are prose here."""\n\n'
        "def check(a, b, xs):\n"
        "    flags = [a == b, a != b, a < b, a >= b, a > b, a <= b]\n"
        "    flags += [a is None, a is not None, a in xs, a not in xs]\n"
        "    return (flags, 0 < a < 10)\n\n"
        "def combine(a, b):\n\n"
        "    def inner(x):\n"
        "        return x * 2 / 4\n"
        "    return ((a and b) and inner(a + b - 1) // 3 % 2, True, False)"
    )
    assert (d / "calc.py").read_text() == expected_calc
    assert (d / "pkg" / "__init__.py").read_bytes() == pkg_before

    # Second scenario: a fresh copy, sites[20] is pkg/__init__.py's comparison.
    second = tmp_path / "second"
    second.mkdir()
    d2 = make_fixture(second)
    calc_before = (d2 / "calc.py").read_bytes()
    sites2 = kind_python.strength_sites(d2)
    assert len(sites2) > 20

    kind_python.apply_site(d2, sites2[20])

    assert (d2 / "pkg" / "__init__.py").read_text() == (
        "def sign(n):\n    return -1 if n >= 0 else 1"
    )
    assert (d2 / "calc.py").read_bytes() == calc_before

    with pytest.raises(ValueError):
        kind_python.apply_site(d2, dict(sites2[0], index=99))
    assert (d2 / "calc.py").read_bytes() == calc_before

    with pytest.raises(ValueError):
        kind_python.apply_site(
            d2, dict(sites2[0], description="calc.py:5: x -> y")
        )
    assert (d2 / "calc.py").read_bytes() == calc_before