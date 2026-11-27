# hotdocs-criterion: sha256:b2b24c25fdd159ec00061a6b83fd48e51a0db20fd830bd5cc627d9db16985101
import shutil

import pytest

import kind_css


S_CSS = (
    ":root {\n"
    "  --c-text: #1f2328;\n"
    "  --c-bg: #ffffff;\n"
    "  --c-gap: 8px;\n"
    "}\n"
    "@media (prefers-color-scheme: dark) {\n"
    "  :root {\n"
    "    --c-bg: #0d1117;\n"
    "  }\n"
    "}\n"
    ".card,\n"
    ".panel {\n"
    "  padding: var(--c-gap);\n"
    "  color: var(--c-text);\n"
    "}\n"
    ".card.tone-ok:hover { border-left: 4px  solid  green }\n"
)


STRONG = [
    ("tokens", [], {"--c-text": "#1f2328", "--c-bg": "#ffffff", "--c-gap": "8px"}),
    ("tokens", ["dark"], {"--c-bg": "#0d1117"}),
    ("rule", [".card, .panel"], {"padding": "var(--c-gap)", "color": "var(--c-text)"}),
    ("rule", [".card.tone-ok:hover"], {"border-left": "4px solid green"}),
]

WEAK = [STRONG[0], STRONG[2]]

BAR = 0.8


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def suite_passes(path, suite):
    run = kind_css.asset_runner(path)
    for entry, args, expected in suite:
        try:
            got = run(entry, list(args))
        except kind_css.AssetError:
            return False
        if got != expected:
            return False
    return True


def write_s_css(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "s.css"
    path.write_text(S_CSS, encoding="utf-8")
    return path


def score(tmp_path, original, sites, suite, label):
    killed = 0
    survivors = []
    for i, site in enumerate(sites):
        copy_dir = tmp_path / (label + "_mutant_" + str(i))
        copy_dir.mkdir(parents=True)
        copy = copy_dir / "s.css"
        shutil.copyfile(original, copy)
        kind_css.apply_site(copy, site)
        if suite_passes(copy, suite):
            survivors.append(field(site, "description"))
        else:
            killed += 1
    return killed, survivors


def test_ac_kcss_009_calibration_pair(tmp_path):
    original = write_s_css(tmp_path / "orig")

    # Each suite passes on the unmutated asset.
    assert suite_passes(original, STRONG)
    assert suite_passes(original, WEAK)

    sites = kind_css.strength_sites(original)
    assert len(sites) == 7

    strong_killed, strong_survivors = score(tmp_path, original, sites, STRONG, "strong")
    assert strong_killed == 7
    assert strong_survivors == []
    assert strong_killed / len(sites) == 1.0
    assert strong_killed / len(sites) >= BAR

    weak_killed, weak_survivors = score(tmp_path, original, sites, WEAK, "weak")
    assert weak_killed == 5
    assert round(weak_killed / len(sites) * 100, 1) == 71.4
    assert weak_killed / len(sites) < BAR
    assert weak_survivors == ["8: --c-bg removed", "16: border-left removed"]

    # The original is left untouched by the mutation runs.
    assert original.read_text(encoding="utf-8") == S_CSS