# hotdocs-criterion: sha256:b20c3e6ffaade9cb902f8767a23398e757bb1e4e151d1a24165eb68f0994a93d
import dataclasses
import json
import re
from pathlib import Path

import provenance_tracker_ui


OPEN_TAG = '<script type="application/json" id="tracker-snapshot">'
CLOSE_TAG = "</script>"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_plain(dataclasses.asdict(value))
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return to_plain(value.to_dict())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return to_plain(dict(vars(value)))
    return value


def normalize(value):
    return json.loads(json.dumps(to_plain(value)))


def passing_component_result():
    return {
        "hit": True,
        "reason": None,
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "mutation_error": None,
            "assets": [
                {
                    "kind": "python",
                    "path": ".",
                    "definition_sha256": None,
                    "adapter_sha256": "sha256:00",
                    "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None,
                }
            ],
            "drivers": [],
            "overall": "pass",
        },
        "license_scan": {"blocked": False, "matches": []},
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def make_report(ready, not_ready_reasons):
    return {
        "scope": "whole-corpus",
        "ready": ready,
        "components": {"comp-foo": passing_component_result()},
        "capabilities": {},
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "not_ready_reasons": not_ready_reasons,
    }


def write_fake_tracker(repo_root, report, log_path):
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import copy\n"
        "\n"
        "_REPORT = " + repr(report) + "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('last_requirement_failures ' + str(component_id) + '\\n')\n"
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
                "sealed": False,
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
    (v / "corpus-graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")


def build(tmp_path, report):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    write_fake_tracker(repo_root, report, log_path)
    write_corpus_graph(repo_root)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
    return repo_root, out_dir, snapshot, log_path


def extract_snapshot(html):
    assert html.count(OPEN_TAG) == 1, "expected exactly one tracker-snapshot element"
    start = html.index(OPEN_TAG) + len(OPEN_TAG)
    end = html.index(CLOSE_TAG, start)
    return html[start:end], start, end


def read_asset():
    asset = Path(provenance_tracker_ui.__file__).resolve().parent / "static" / "app.js"
    return asset.read_text(encoding="utf-8")


def test_single_self_contained_index_html(tmp_path):
    report = make_report(True, [])
    repo_root, out_dir, snapshot, log_path = build(tmp_path, report)

    assert log_path.read_text(encoding="utf-8").splitlines().count("check_readiness") == 1

    entries = sorted(str(p.relative_to(out_dir)) for p in out_dir.rglob("*"))
    assert entries == ["index.html"]
    assert (out_dir / "index.html").is_file()

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    block, _, _ = extract_snapshot(html)
    parsed = json.loads(block)
    assert parsed == normalize(snapshot)
    node_ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert node_ids == ["comp-foo"]

    assert re.search(r'<[A-Za-z][A-Za-z0-9-]*\b[^>]*\bdata-node-id="comp-foo"', html), (
        "no node element with data-node-id=\"comp-foo\""
    )

    asset_text = read_asset()
    assert asset_text in html
    outside = html.replace(asset_text, "", 1)

    assert "fetch(" not in outside
    assert "XMLHttpRequest" not in outside
    assert "WebAssembly" not in outside

    for m in re.finditer(r"""\b(src|href)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", outside, re.IGNORECASE):
        value = (m.group(2) if m.group(2) is not None else
                 m.group(3) if m.group(3) is not None else m.group(4)).strip()
        assert value.startswith("#") or value.lower().startswith("data:"), (
            "external resource reference: " + m.group(0)
        )


def test_script_close_in_reasons_does_not_break_snapshot(tmp_path):
    reason = "comp-foo: weird </script><script>alert(1)</script> reason"
    report = make_report(False, [reason])
    repo_root, out_dir, snapshot, log_path = build(tmp_path, report)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    block, _, _ = extract_snapshot(html)
    parsed = json.loads(block)
    expected = normalize(snapshot)
    assert parsed == expected
    assert reason in field(snapshot, "not_ready_reasons")
    assert parsed["not_ready_reasons"] == [reason]