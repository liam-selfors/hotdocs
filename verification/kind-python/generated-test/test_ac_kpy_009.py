# hotdocs-criterion: sha256:1c2a3597029dacabc261d1bf1bd134205c000532946d6b473f18f72356a750a6
import kind_python


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


CALC_SOURCE = (
    '"""Calculator: a < b and True are prose here."""\n' "\n" "\n"
    "def check(a, b, xs):\n"
    "    flags = [a == b, a != b, a < b, a >= b, a > b, a <= b]\n"
    "    flags += [a is None, a is not None, a in xs, a not in xs]\n"
    "    return flags, 0 < a < 10\n" "\n" "\n"
    "def combine(a, b):\n" "    def inner(x):\n" "        return x * 2 / 4\n"
    "    return (a and b) or inner(a + b - 1) // 3 % 2, True, False\n"
)

PKG_INIT_SOURCE = "def sign(n):\n    return -1 if n < 0 else 1\n"

JUNK_SOURCE = "x = 1 == 2\n"

EXPECTED_DESCRIPTIONS = [
    "calc.py:5: a == b -> a != b",
    "calc.py:5: a != b -> a == b",
    "calc.py:5: a < b -> a >= b",
    "calc.py:5: a >= b -> a < b",
    "calc.py:5: a > b -> a <= b",
    "calc.py:5: a <= b -> a > b",
    "calc.py:6: a is None -> a is not None",
    "calc.py:6: a is not None -> a is None",
    "calc.py:6: a in xs -> a not in xs",
    "calc.py:6: a not in xs -> a in xs",
    "calc.py:12: x * 2 / 4 -> x * 2 * 4",
    "calc.py:13: a and b or inner(a + b - 1) // 3 % 2 -> (a and b) and inner(a + b - 1) // 3 % 2",
    "calc.py:13: True -> False",
    "calc.py:13: False -> True",
    "calc.py:12: x * 2 -> x / 2",
    "calc.py:13: a and b -> a or b",
    "calc.py:13: inner(a + b - 1) // 3 % 2 -> inner(a + b - 1) // 3 // 2",
    "calc.py:13: inner(a + b - 1) // 3 -> inner(a + b - 1) % 3",
    "calc.py:13: a + b - 1 -> a + b + 1",
    "calc.py:13: a + b -> a - b",
    "pkg/__init__.py:2: n < 0 -> n >= 0",
]


def build_code_dir(tmp_path):
    d = tmp_path / "calc"
    d.mkdir()
    (d / "calc.py").write_text(CALC_SOURCE, encoding="utf-8")
    (d / "pkg").mkdir()
    (d / "pkg" / "__init__.py").write_text(PKG_INIT_SOURCE, encoding="utf-8")
    (d / "__pycache__").mkdir()
    (d / "__pycache__" / "junk.py").write_text(JUNK_SOURCE, encoding="utf-8")
    return d


def test_ac_kpy_009_strength_sites_parity(tmp_path):
    d = build_code_dir(tmp_path)

    sites = kind_python.strength_sites(d)

    assert isinstance(sites, list)

    descriptions = [field(site, "description") for site in sites]
    assert descriptions == EXPECTED_DESCRIPTIONS

    files = [field(site, "file") for site in sites]
    assert files == ["calc.py"] * 20 + ["pkg/__init__.py"]

    indexes = [field(site, "index") for site in sites]
    assert indexes == list(range(20)) + [0]

    for site in sites:
        assert isinstance(site, dict)
        assert set(site.keys()) == {"description", "file", "index"}

    # Nothing from __pycache__, the docstring, the chained comparison,
    # numeric constants, +=, or the unary -1.
    for desc in descriptions:
        assert "__pycache__" not in desc
        assert "prose" not in desc
        assert "0 < a < 10" not in desc
        assert "-1 ->" not in desc