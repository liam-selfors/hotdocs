# hotdocs-criterion: sha256:770e6a1f3b7af1210507040bfc0ea382e6df0a72cad2aae7756b13643a1b9e63
import shutil
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

BAR = 0.8


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def suite_kills(run, suite):
    for entry, args, expected in suite:
        try:
            result = run(entry, list(args))
        except kind_javascript.AssetError:
            return True
        if result != expected:
            return True
    return False


def fresh_copy(tmp_path, original, label):
    d = tmp_path / label
    d.mkdir()
    dest = d / "c.js"
    shutil.copyfile(original, dest)
    return dest


def killed_descriptions(tmp_path, original, sites, suite, label):
    killed = []
    survivors = []
    for i, site in enumerate(sites):
        copy = fresh_copy(tmp_path, original, label + "_" + str(i))
        kind_javascript.apply_site(copy, site)
        run = kind_javascript.asset_runner(copy)
        if suite_kills(run, suite):
            killed.append(field(site, "description"))
        else:
            survivors.append(field(site, "description"))
    return killed, survivors


def test_ac_kjs_012_calibration_pair(tmp_path):
    original = tmp_path / "c.js"
    original.write_text(SOURCE, encoding="utf-8")

    sites = kind_javascript.strength_sites(original)
    descriptions = [field(s, "description") for s in sites]
    assert descriptions == EXPECTED_DESCRIPTIONS

    # Each suite passes on the unmutated asset.
    for label, suite in (("base_strong", STRONG), ("base_weak", WEAK)):
        copy = fresh_copy(tmp_path, original, label)
        run = kind_javascript.asset_runner(copy)
        for entry, args, expected in suite:
            assert run(entry, list(args)) == expected, (label, entry, args)

    # strength_sites must not have modified the original.
    assert original.read_text(encoding="utf-8") == SOURCE

    strong_killed, strong_survivors = killed_descriptions(
        tmp_path, original, sites, STRONG, "strong"
    )
    weak_killed, weak_survivors = killed_descriptions(
        tmp_path, original, sites, WEAK, "weak"
    )

    total = len(sites)
    assert total == 6

    assert len(strong_killed) == 6
    assert strong_survivors == []
    assert len(strong_killed) / total >= BAR

    assert len(weak_killed) == 4
    assert len(weak_killed) / total == pytest.approx(4 / 6)
    assert len(weak_killed) / total < BAR
    assert weak_survivors == ["8: && -> ||", "13: + -> -"]