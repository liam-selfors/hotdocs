# hotdocs-criterion: sha256:0b74ac12dfa2178df2aaad8f44fc3fb48fb8539667604d8466d01845afd036ad
import json
import re

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall):
    req = "R-" + component_id.upper().replace("COMP-", "") + "-001"
    result = "pass" if overall == "pass" else "fail"
    crit = {
        "id": "AC-" + component_id.upper().replace("COMP-", "") + "-001",
        "covers": req,
        "kind": "compiled",
        "result": result,
    }
    if result == "fail":
        crit["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
        crit["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [crit],
        "requirement_results": {req: result},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _license_scan():
    return {"blocked": False, "matches": [], "gate_version": "license_scanner@1.0.0"}


def _provenance_hit(component_id, overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


def _write_fake_tracker(repo_root, log_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-bar": _provenance_hit("comp-bar", "fail"),
            "comp-foo": _provenance_hit("comp-foo", "pass"),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": ["comp-bar: verification failed"],
    }
    src = (
        "import copy\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    report = copy.deepcopy(REPORT)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return report\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
    )
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    (d / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _component_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-bar": _component_node(),
            "comp-foo": _component_node(),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    d = repo_root / "verification"
    d.mkdir(parents=True, exist_ok=True)
    (d / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


_RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def _parse_rgb(value):
    m = _RGB_RE.match(value.strip())
    assert m, "not an rgb() colour: " + repr(value)
    return tuple(int(x) for x in m.groups())


def _luminance(rgb):
    chans = []
    for v in rgb:
        c = v / 255
        c = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        chans.append(c)
    r, g, b = chans
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def _check_opening(page):
    foo = page.find(css='li.node[data-node-id="comp-foo"]')
    bar = page.find(css='li.node[data-node-id="comp-bar"]')

    foo_classes = (foo.attribute("class") or "").split()
    bar_classes = (bar.attribute("class") or "").split()
    assert "node" in foo_classes
    assert "node" in bar_classes
    assert "tone-ok" in foo_classes, foo_classes
    assert "tone-fail" in bar_classes, bar_classes

    assert foo.style("border-left-width") == "4px"
    assert bar.style("border-left-width") == "4px"

    foo_color = _parse_rgb(foo.style("border-left-color"))
    bar_color = _parse_rgb(bar.style("border-left-color"))
    assert foo_color != bar_color

    bg_raw = page.find(css="body").style("background-color")
    bg = _parse_rgb(bg_raw)
    assert _contrast(foo_color, bg) >= 3, (foo_color, bg)
    assert _contrast(bar_color, bg) >= 3, (bar_color, bg)

    assert page.console_errors() == []
    return bg


def test_ac_ui_013_tone_classes_and_contrast_light_and_dark(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines.count("check_readiness") == 1

    statuses = {field(n, "id"): field(n, "status") for n in field(snapshot, "nodes")}
    assert statuses == {"comp-bar": "failing", "comp-foo": "passing"}

    index = out_dir / "index.html"
    assert index.is_file()

    light_page = browser.open(index)
    light_bg = _check_opening(light_page)

    dark_page = browser.open(index, color_scheme="dark")
    dark_bg = _check_opening(dark_page)

    assert light_bg != dark_bg