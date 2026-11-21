# hotdocs-criterion: sha256:994543918db773f3e5a4795dd8d4ff21401229a46c51779a77550b546e493616
import kind_python


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


CALC_PY = (
    '"""Calculator: a < b and True are prose here."""\n' "\n" "\n"
    "def check(a, b, xs):\n"
    "    flags = [a == b, a != b, a < b, a >= b, a > b, a <= b]\n"
    "    flags += [a is None, a is not None, a in xs, a not in xs]\n"
    "    return flags, 0 < a < 10\n" "\n" "\n"
    "def combine(a, b):\n" "    def inner(x):\n" "        return x * 2 / 4\n"
    "    return (a and b) or inner(a + b - 1) // 3 % 2, True, False\n"
)

PKG_INIT_PY = "def sign(n):\n    return -1 if n < 0 else 1\n"

JUNK_PY = "x = 1 == 2\n"

EXPECTED = [
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_ac_kpy_009_strength_sites_parity(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    d = tmp_path / "calc"
    _write(d / "calc.py", CALC_PY)
    _write(d / "pkg" / "__init__.py", PKG_INIT_PY)
    _write(d / "__pycache__" / "junk.py", JUNK_PY)

    sites = kind_python.strength_sites(d)
    sites = list(sites)

    descriptions = [field(s, "description") for s in sites]
    assert descriptions == EXPECTED

    files = [field(s, "file") for s in sites]
    assert files == ["calc.py"] * 20 + ["pkg/__init__.py"]

    indexes = [field(s, "index") for s in sites]
    assert indexes == list(range(20)) + [0]

    for s in sites:
        assert isinstance(s, dict)
        assert set(s.keys()) == {"description", "file", "index"}