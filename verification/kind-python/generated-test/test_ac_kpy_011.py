# hotdocs-criterion: sha256:963073abb04de0db3ca422c2c8b2979ad6aa7717e2d9e9b5ef14b17dac77d314
import shutil

import pytest

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


def killed_by(run, suite):
    for entry, args, expected in suite:
        try:
            result = run(entry, args)
        except kind_python.AssetError:
            return True
        if result != expected:
            return True
    return False


def test_ac_kpy_011_calibration_pair(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    code_dir = tmp_path / "grade"
    code_dir.mkdir(parents=True)
    (code_dir / "grade.py").write_text(GRADE_SOURCE, encoding="utf-8")

    sites = kind_python.strength_sites(code_dir)
    descriptions = [field(s, "description") for s in sites]
    assert descriptions == EXPECTED_DESCRIPTIONS

    # Each suite passes unmutated.
    run = kind_python.asset_runner(code_dir)
    for suite in (STRONG, WEAK):
        for entry, args, expected in suite:
            assert run(entry, args) == expected

    strong_killed = []
    weak_survivors = []
    weak_killed = []
    for i, site in enumerate(sites):
        copy = tmp_path / ("m" + str(i)) / "grade"
        copy.parent.mkdir(parents=True)
        shutil.copytree(code_dir, copy)
        kind_python.apply_site(copy, site)
        mutant_run = kind_python.asset_runner(copy)
        desc = field(site, "description")
        if killed_by(mutant_run, STRONG):
            strong_killed.append(desc)
        if killed_by(mutant_run, WEAK):
            weak_killed.append(desc)
        else:
            weak_survivors.append(desc)

    total_sites = len(sites)
    assert total_sites == 6

    assert len(strong_killed) == 6
    assert len(strong_killed) / total_sites >= BAR

    assert len(weak_killed) == 4
    assert len(weak_killed) / total_sites < BAR
    assert round(100 * len(weak_killed) / total_sites, 1) == 66.7
    assert weak_survivors == [
        "grade.py:10: a == b and a > 0 -> a == b or a > 0",
        "grade.py:16: s + x -> s - x",
    ]