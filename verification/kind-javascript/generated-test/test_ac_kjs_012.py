# hotdocs-criterion: sha256:cac741d0b723283061368bc190e755898312dc6207da45e7bdbe246a1c51fa2b
import shutil
from pathlib import Path

import kind_javascript


C_JS = (
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def kills(run, suite):
    for entry, args, expected in suite:
        try:
            result = run(entry, args)
        except kind_javascript.AssetError:
            return True
        if result != expected:
            return True
    return False


def test_ac_kjs_012_calibration_pair(tmp_path):
    c_js = tmp_path / "c.js"
    c_js.write_text(C_JS, encoding="utf-8")

    sites = kind_javascript.strength_sites(c_js)
    descriptions = [field(s, "description") for s in sites]
    assert descriptions == EXPECTED_DESCRIPTIONS

    # Each suite passes on the unmutated file.
    run = kind_javascript.asset_runner(c_js)
    for suite in (STRONG, WEAK):
        for entry, args, expected in suite:
            assert run(entry, args) == expected, (entry, args, expected)

    strong_killed = []
    weak_killed = []
    for index, site in enumerate(sites):
        site_dir = tmp_path / ("mutant_" + str(index))
        site_dir.mkdir()
        copy = site_dir / "c.js"
        shutil.copyfile(c_js, copy)
        kind_javascript.apply_site(copy, site)
        mutant_run = kind_javascript.asset_runner(copy)
        description = field(site, "description")
        if kills(mutant_run, STRONG):
            strong_killed.append(description)
        if kills(mutant_run, WEAK):
            weak_killed.append(description)

    total = len(sites)
    assert total == 6

    assert len(strong_killed) == 6
    assert len(strong_killed) / total >= 0.8

    assert len(weak_killed) == 4
    assert len(weak_killed) / total < 0.8
    survivors = [d for d in descriptions if d not in weak_killed]
    assert survivors == ["8: && -> ||", "13: + -> -"]