# hotdocs-criterion: sha256:3fff891ffc3caafc8033031e3304be42d0a0c92e5777ff27fe943a86687d9be4
import shutil
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

PKG_INIT_SRC = (
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(root):
    _write(root / "calc.py", CALC_SRC)
    _write(root / "pkg" / "__init__.py", PKG_INIT_SRC)
    return root


def test_ac_kpy_010(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    src = _build_fixture(tmp_path / "src" / "demo")

    # First scenario: apply site 11 (in calc.py).
    d = tmp_path / "one" / "demo"
    shutil.copytree(src, d)
    pkg_before = (d / "pkg" / "__init__.py").read_bytes()
    sites = kind_python.strength_sites(d)
    kind_python.apply_site(d, sites[11])
    assert (d / "calc.py").read_text(encoding="utf-8") == EXPECTED_CALC_AFTER_11
    assert (d / "pkg" / "__init__.py").read_bytes() == pkg_before

    # Second scenario: fresh copy, apply site 20 (in pkg/__init__.py).
    d2 = tmp_path / "two" / "demo"
    shutil.copytree(src, d2)
    sites2 = kind_python.strength_sites(d2)
    calc_before = (d2 / "calc.py").read_bytes()
    kind_python.apply_site(d2, sites2[20])
    assert (
        (d2 / "pkg" / "__init__.py").read_text(encoding="utf-8")
        == EXPECTED_PKG_AFTER_20
    )
    assert (d2 / "calc.py").read_bytes() == calc_before

    # Invalid sites raise ValueError and leave calc.py unchanged.
    with pytest.raises(ValueError):
        kind_python.apply_site(d2, dict(sites2[0], index=99))
    assert (d2 / "calc.py").read_bytes() == calc_before

    with pytest.raises(ValueError):
        kind_python.apply_site(
            d2, dict(sites2[0], description="calc.py:5: x -> y")
        )
    assert (d2 / "calc.py").read_bytes() == calc_before