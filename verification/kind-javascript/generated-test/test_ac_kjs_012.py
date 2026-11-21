# hotdocs-criterion: sha256:0be7650560d613981bc89ab8a9bf9b9a1bb290226605b7024caded484536db2b
import shutil

import kind_javascript


C_JS_LINES = [
    "export function grade(score) {\n",
    "  if (score >= 90) return \"A\";\n",
    "  if (score >= 75) return \"B\";\n",
    "  return \"C\";\n",
    "}\n",
    "\n",
    "export function both(a, b) {\n",
    "  return a === b && a > 0;\n",
    "}\n",
    "\n",
    "export function total(xs) {\n",
    "  let s = 0;\n",
    "  for (const x of xs) s = s + x;\n",
    "  return s;\n",
    "}\n",
]
C_JS = "".join(C_JS_LINES)

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


def suite_kills(run, suite):
    for entry, args, expected in suite:
        try:
            result = run(entry, list(args))
        except kind_javascript.AssetError:
            return True
        if result != expected:
            return True
    return False


def score_suite(tmp_path, original, sites, suite, label):
    killed = []
    survivors = []
    for index, site in enumerate(sites):
        copy_dir = tmp_path / ("mutant_" + label + "_" + str(index))
        copy_dir.mkdir()
        copy = copy_dir / "c.js"
        shutil.copyfile(original, copy)
        kind_javascript.apply_site(copy, site)
        run = kind_javascript.asset_runner(copy)
        if suite_kills(run, suite):
            killed.append(field(site, "description"))
        else:
            survivors.append(field(site, "description"))
    return killed, survivors


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
            assert run(entry, list(args)) == expected

    # The original file is unchanged by the checks.
    assert c_js.read_text(encoding="utf-8") == C_JS

    strong_killed, strong_survivors = score_suite(tmp_path, c_js, sites, STRONG, "strong")
    assert len(strong_killed) == 6
    assert strong_survivors == []
    assert len(strong_killed) / len(sites) >= 0.8

    weak_killed, weak_survivors = score_suite(tmp_path, c_js, sites, WEAK, "weak")
    assert len(weak_killed) == 4
    assert len(weak_killed) / len(sites) < 0.8
    assert weak_survivors == ["8: && -> ||", "13: + -> -"]