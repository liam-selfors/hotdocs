# hotdocs-criterion: sha256:f5f6fa9f92de88c5da06bcd0322a2fd26f4e4683e6b8edbd6727eec65733695d
import shutil

import kind_python


GRADE_SOURCE = (
    "def grade(score):\n"
    "    if score >= 90:\n"
    "        return \"A\"\n"
    "    if score >= 75:\n"
    "        return \"B\"\n"
    "    return \"C\"\n"
    "\n"
    "\n"
    "def both(a, b):\n"
    "    return a == b and a > 0\n"
    "\n"
    "\n"
    "def total(xs):\n"
    "    s = 0\n"
    "    for x in xs:\n"
    "        s = s + x\n"
    "    return s\n"
)

STRONG = [
    ("grade", [95], "A"),
    ("grade", [80], "B"),
    ("grade", [50], "C"),
    ("both", [2, 2], True),
    ("both", [2, 3], False),
    ("both", [-1, -1], False),
    ("total", [[1, 2, 3]], 6),
]

WEAK = [
    ("grade", [95], "A"),
    ("grade", [80], "B"),
    ("both", [2, 2], True),
    ("total", [[]], 0),
]

EXPECTED_DESCRIPTIONS = [
    "grade.py:2: score >= 90 -> score < 90",
    "grade.py:4: score >= 75 -> score < 75",
    "grade.py:10: a == b and a > 0 -> a == b or a > 0",
    "grade.py:10: a == b -> a != b",
    "grade.py:10: a > 0 -> a <= 0",
    "grade.py:16: s + x -> s - x",
]

BAR = 0.8


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def suite_kills(run, suite):
    for entry, args, expected in suite:
        try:
            result = run(entry, list(args))
        except kind_python.AssetError:
            return True
        if result != expected:
            return True
    return False


def test_ac_kpy_011_calibration_pair(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")

    code_dir = tmp_path / "grade"
    code_dir.mkdir()
    (code_dir / "grade.py").write_text(GRADE_SOURCE, encoding="utf-8")

    sites = kind_python.strength_sites(code_dir)
    descriptions = [field(site, "description") for site in sites]
    assert descriptions == EXPECTED_DESCRIPTIONS

    # Each suite passes unmutated.
    run = kind_python.asset_runner(code_dir)
    for suite in (STRONG, WEAK):
        for entry, args, expected in suite:
            assert run(entry, list(args)) == expected, (entry, args, expected)

    strong_killed = []
    weak_survivors = []
    weak_killed = []
    for i, site in enumerate(sites):
        copy_dir = tmp_path / ("m" + str(i)) / "grade"
        shutil.copytree(
            code_dir, copy_dir, ignore=shutil.ignore_patterns("__pycache__")
        )
        kind_python.apply_site(copy_dir, site)
        mutant_run = kind_python.asset_runner(copy_dir)
        description = field(site, "description")
        if suite_kills(mutant_run, STRONG):
            strong_killed.append(description)
        if suite_kills(mutant_run, WEAK):
            weak_killed.append(description)
        else:
            weak_survivors.append(description)

    total = len(sites)
    assert total == 6

    assert len(strong_killed) == 6, strong_killed
    assert len(strong_killed) / total >= BAR

    assert len(weak_killed) == 4, weak_killed
    assert len(weak_killed) / total < BAR
    assert weak_survivors == [
        "grade.py:10: a == b and a > 0 -> a == b or a > 0",
        "grade.py:16: s + x -> s - x",
    ]