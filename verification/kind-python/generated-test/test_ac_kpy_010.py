# hotdocs-criterion: sha256:d3c6437f576318fe0b3131070c89ef5709af38e30dae854c1ec5809f496f6974
import shutil
from pathlib import Path

import pytest

import kind_python


CALC_SOURCE = (
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
    "    return (a and b or inner(a + b - 1) // 3 % 2, True, False)\n"
)

PKG_INIT_SOURCE = (
    "def sign(n):\n"
    "    return -1 if n < 0 else 1\n"
)

EXPECTED_CALC_AFTER_11 = (
    '"""Calculator: a < b and True are prose here."""\n\ndef check(a, b, xs):\n'
    "    flags = [a == b, a != b, a < b, a >= b, a > b, a <= b]\n"
    "    flags += [a is None, a is not None, a in xs, a not in xs]\n"
    "    return (flags, 0 < a < 10)\n\ndef combine(a, b):\n\n    def inner(x):\n"
    "        return x * 2 / 4\n"
    "    return ((a and b) and inner(a + b - 1) // 3 % 2, True, False)"
)

EXPECTED_PKG_AFTER_20 = "def sign(n):\n    return -1 if n >= 0 else 1"


def write_file(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(root):
    d = root / "demo-code"
    d.mkdir(parents=True)
    write_file(d / "calc.py", CALC_SOURCE)
    write_file(d / "pkg" / "__init__.py", PKG_INIT_SOURCE)
    return d


def test_ac_kpy_010(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    src = build_fixture(tmp_path / "src")

    # Scenario 1: apply site 11 on a copy of the fixture.
    d = tmp_path / "one" / "demo-code"
    d.parent.mkdir(parents=True)
    shutil.copytree(src, d)
    sites = kind_python.strength_sites(d)
    pkg_before = (d / "pkg" / "__init__.py").read_bytes()

    kind_python.apply_site(d, sites[11])

    assert (d / "calc.py").read_text(encoding="utf-8") == EXPECTED_CALC_AFTER_11
    assert (d / "pkg" / "__init__.py").read_bytes() == pkg_before

    # Scenario 2: a fresh copy and its sites; apply site 20.
    d2 = tmp_path / "two" / "demo-code"
    d2.parent.mkdir(parents=True)
    shutil.copytree(src, d2)
    sites2 = kind_python.strength_sites(d2)
    calc_before = (d2 / "calc.py").read_bytes()

    kind_python.apply_site(d2, sites2[20])

    assert (d2 / "pkg" / "__init__.py").read_text(encoding="utf-8") == EXPECTED_PKG_AFTER_20
    assert (d2 / "calc.py").read_bytes() == calc_before

    # Mismatched sites raise ValueError and leave calc.py unchanged.
    with pytest.raises(ValueError):
        kind_python.apply_site(d2, dict(sites2[0], index=99))
    assert (d2 / "calc.py").read_bytes() == calc_before

    with pytest.raises(ValueError):
        kind_python.apply_site(d2, dict(sites2[0], description="calc.py:5: x -> y"))
    assert (d2 / "calc.py").read_bytes() == calc_before