# hotdocs-criterion: sha256:82a3fe0cdae917e4bfe92509c4e5feaae2bb4a72b0efe3559704e77d91b6f5c9
import json
import re
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall):
    req = "R-" + component_id.upper().replace("COMP-", "") + "-001"
    result = "pass" if overall == "pass" else "fail"
    criterion = {
        "id": "AC-" + component_id.upper().replace("COMP-", "") + "-001",
        "covers": req,
        "kind": "compiled",
        "result": result,
    }
    if result == "fail":
        criterion["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
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


def _check_result(component_id, overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": {"blocked": False, "matches": []},
        "secret_scan": _secret_scan(),
    }


def _write_fake_tracker(repo_root, log_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _check_result("comp-foo", "pass"),
            "comp-bar": _check_result("comp-bar", "fail"),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": ["comp-bar: verification failed"],
    }
    src = (
        "import copy\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    result = copy.deepcopy(REPORT)\n"
        "    result['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return result\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('last_requirement_failures ' + str(component_id) + '\\n')\n"
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
            "orphan_component_rate": 1.0,
            "orphan_var_rate": 0.0,
        },
    }
    d = repo_root / "verification"
    d.mkdir(parents=True, exist_ok=True)
    (d / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _parse_rgb(value):
    nums = re.findall(r"[-+]?\d*\.?\d+", value)
    assert len(nums) >= 3, "not an rgb() colour: " + repr(value)
    return tuple(int(round(float(n))) for n in nums[:3])


def _channel(v):
    c = v / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb):
    r, g, b = (_channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def _check_opening(page):
    foo = page.find(css='li.node[data-node-id="comp-foo"]')
    bar = page.find(css='li.node[data-node-id="comp-bar"]')
    assert foo.count() == 1
    assert bar.count() == 1

    foo_classes = (foo.attribute("class") or "").split()
    bar_classes = (bar.attribute("class") or "").split()
    assert "node" in foo_classes
    assert "node" in bar_classes
    assert "tone-ok" in foo_classes
    assert "tone-fail" in bar_classes

    assert foo.style("border-left-width") == "4px"
    assert bar.style("border-left-width") == "4px"

    foo_color = foo.style("border-left-color")
    bar_color = bar.style("border-left-color")
    assert foo_color != bar_color

    bg = page.find(css="body").style("background-color")
    bg_rgb = _parse_rgb(bg)
    assert _contrast(_parse_rgb(foo_color), bg_rgb) >= 3, (foo_color, bg)
    assert _contrast(_parse_rgb(bar_color), bg_rgb) >= 3, (bar_color, bg)

    assert page.console_errors() == []
    return bg


def test_ac_ui_013_tone_borders_contrast_in_light_and_dark(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    statuses = {field(n, "id"): field(n, "status") for n in field(snapshot, "nodes")}
    assert statuses == {"comp-bar": "failing", "comp-foo": "passing"}

    index = out_dir / "index.html"
    assert index.is_file()

    light_page = browser.open(index)
    light_bg = _check_opening(light_page)

    dark_page = browser.open(index, color_scheme="dark")
    dark_bg = _check_opening(dark_page)

    assert light_bg != dark_bg