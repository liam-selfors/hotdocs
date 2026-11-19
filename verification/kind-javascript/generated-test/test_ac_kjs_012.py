# hotdocs-criterion: sha256:0628903587a0085e592b8dc9b37487ed7cb255fcc5c6f93e31046ae3d961392c
from pathlib import Path

import pytest

import kind_javascript


SOURCE = (
    "export function grade(score) {\n"
    "  if (score >= 90) return \"A\";\n"
    "  if (score >= 75) return \"B\";\n"
    "  return \"C\";\n"
    "}\n"
    "\n"
    "export function both(a, b) {\n"
    "  return a === b && a > 0;\n"
    "}\n"
    "\n"
    "export function total(xs) {\n"
    "  let s = 0;\n"
    "  for (const x of xs) s = s + x;\n"
    "  return s;\n"
    "}\n"
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
    "2: >= -> <",
    "3: >= -> <",
    "8: === -> !==",
    "8: && -> ||",
    "8: > -> <=",
    "13: + -> -",
]

BAR = 80.0


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_source(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SOURCE, encoding="utf-8")
    return path


def same_value(actual, expected):
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(actual) is type(expected) and actual == expected
    return actual == expected


def suite_kills(run, suite):
    for entry, args, expected in suite:
        try:
            got = run(entry, args)
        except kind_javascript.AssetError:
            return True
        if not same_value(got, expected):
            return True
    return False


def test_ac_kjs_012_calibration_pair(tmp_path):
    asset = write_source(tmp_path / "c.js")

    sites = kind_javascript.strength_sites(asset)
    descriptions = [field(s, "description") for s in sites]
    assert descriptions == EXPECTED_DESCRIPTIONS

    # Each suite passes on the unmutated asset.
    run = kind_javascript.asset_runner(asset)
    for suite in (STRONG, WEAK):
        for entry, args, expected in suite:
            got = run(entry, args)
            assert same_value(got, expected), (entry, args, got, expected)

    strong_killed = []
    weak_killed = []
    for index, site in enumerate(sites):
        mutant = write_source(tmp_path / ("mutant" + str(index)) / "c.js")
        kind_javascript.apply_site(mutant, site)
        assert mutant.read_text(encoding="utf-8") != SOURCE
        mrun = kind_javascript.asset_runner(mutant)
        description = field(site, "description")
        if suite_kills(mrun, STRONG):
            strong_killed.append(description)
        if suite_kills(mrun, WEAK):
            weak_killed.append(description)

    total = len(sites)
    assert total == 6

    strong_score = 100.0 * len(strong_killed) / total
    weak_score = 100.0 * len(weak_killed) / total

    assert len(strong_killed) == 6
    assert strong_score == 100.0
    assert strong_score >= BAR

    assert len(weak_killed) == 4
    assert round(weak_score, 1) == 66.7
    assert weak_score < BAR

    weak_survivors = [d for d in descriptions if d not in weak_killed]
    assert weak_survivors == ["8: && -> ||", "13: + -> -"]