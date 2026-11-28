# hotdocs-criterion: sha256:db655b4337a15a75e054d2701250c3561b3a55e3721ebed21701c6ffeeee888f
import dataclasses
import json
import re
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return to_plain(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_plain(dataclasses.asdict(value))
    return value


SNAPSHOT_OPEN = '<script type="application/json" id="tracker-snapshot">'


def verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


def secret_scan_result():
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


def verify_report(ready, reasons):
    return {
        "scope": "whole-corpus",
        "ready": ready,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report(),
                "license_scan": {"blocked": False},
                "secret_scan": secret_scan_result(),
            }
        },
        "capabilities": {},
        "secret_scan": secret_scan_result(),
        "not_ready_reasons": reasons,
    }


def write_fake_tracker(repo_root, report, log_path):
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "\n"
        "REPORT = json.loads(" + repr(json.dumps(report)) + ")\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('check_readiness\\n')\n"
        "    return json.loads(json.dumps(REPORT))\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('last_requirement_failures ' + str(component_id) + '\\n')\n"
        "    return []\n"
    )
    (d / "provenance_tracker.py").write_text(src, encoding="utf-8")


def write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            }
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    v = repo_root / "verification"
    v.mkdir(parents=True, exist_ok=True)
    (v / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def build(tmp_path, ready, reasons):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    write_fake_tracker(repo_root, verify_report(ready, reasons), log_path)
    write_corpus_graph(repo_root)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
    return out_dir, snapshot, log_path


def extract_snapshot_json(html):
    assert html.count(SNAPSHOT_OPEN) == 1
    start = html.index(SNAPSHOT_OPEN) + len(SNAPSHOT_OPEN)
    end = html.index("</script>", start)
    return json.loads(html[start:end])


def app_js_text():
    path = Path(provenance_tracker_ui.__file__).resolve().parent / "static" / "app.js"
    return path.read_text(encoding="utf-8")


def test_single_self_contained_index_html(tmp_path):
    out_dir, snapshot, log_path = build(tmp_path, True, [])

    assert log_path.read_text(encoding="utf-8").splitlines().count("check_readiness") == 1

    assert sorted(p.name for p in out_dir.iterdir()) == ["index.html"]
    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    expected = json.loads(json.dumps(to_plain(snapshot)))
    assert extract_snapshot_json(html) == expected

    ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert ids == ["comp-foo"]

    assert 'data-node-id="comp-foo"' in html

    app_text = app_js_text()
    assert app_text in html
    outside = html.replace(app_text, "", 1)

    assert "fetch(" not in outside
    assert "XMLHttpRequest" not in outside
    assert "WebAssembly" not in outside

    attr_re = re.compile(r"""\b(src|href)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
    for m in attr_re.finditer(outside):
        value = (m.group(2) or m.group(3) or m.group(4) or "").strip()
        assert value.startswith("#") or value.lower().startswith("data:"), (
            "external resource reference: " + m.group(0)
        )


def test_script_close_in_reason_is_escaped(tmp_path):
    reason = "comp-foo: odd </script><script>alert(1)</script> text"
    out_dir, snapshot, _ = build(tmp_path, False, [reason])

    assert list(field(snapshot, "not_ready_reasons")) == [reason]

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    expected = json.loads(json.dumps(to_plain(snapshot)))
    parsed = extract_snapshot_json(html)
    assert parsed == expected
    assert parsed["not_ready_reasons"] == [reason]