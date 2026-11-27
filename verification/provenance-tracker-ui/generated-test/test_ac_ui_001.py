# hotdocs-criterion: sha256:2fbeae41950e7f953e8c5aa0d5d77501c5d38ea1a51d5517b1eb269453113c49
import dataclasses
import json
import re
from pathlib import Path

import provenance_tracker_ui


SNAPSHOT_OPEN = '<script type="application/json" id="tracker-snapshot">'


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return normalize(dataclasses.asdict(value))
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return normalize(value.to_dict())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return normalize(vars(value))
    return value


def snapshot_as_json(snapshot):
    return json.loads(json.dumps(normalize(snapshot)))


def verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
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


def make_report(ready, not_ready_reasons):
    return {
        "scope": "whole-corpus",
        "ready": ready,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report(),
                "license_scan": {
                    "gate_version": "license_scanner@1.0.0",
                    "blocked": False,
                    "matches": [],
                    "cache_hit": False,
                },
                "secret_scan": secret_scan_result(),
            }
        },
        "capabilities": {},
        "secret_scan": secret_scan_result(),
        "not_ready_reasons": list(not_ready_reasons),
    }


def write_fixture(repo_root, report, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "REPORT_JSON = " + repr(json.dumps(report)) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(REPORT_JSON)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise RuntimeError('not used by this test')\n"
        "\n"
        "def main(argv=None):\n"
        "    return 2\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            }
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 1.0,
            "orphan_var_rate": 0.0,
        },
    }
    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def extract_snapshot_block(html):
    assert html.count('id="tracker-snapshot"') == 1, "tracker-snapshot must be inlined exactly once"
    start = html.index(SNAPSHOT_OPEN) + len(SNAPSHOT_OPEN)
    end = html.index("</script>", start)
    return html[start:end]


def run_render(tmp_path, report):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    write_fixture(repo_root, report, log_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
    assert log_path.is_file(), "the faked provenance-tracker was not called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()
    return out_dir, snapshot


def is_external(value):
    v = value.strip()
    if v == "" or v.startswith("#"):
        return False
    if v.lower().startswith("data:"):
        return False
    return True


def test_single_self_contained_index_html(tmp_path):
    out_dir, snapshot = run_render(tmp_path, make_report(True, []))

    files = sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file())
    assert files == ["index.html"]
    entries = sorted(p.name for p in out_dir.iterdir())
    assert entries == ["index.html"]

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    block = extract_snapshot_block(html)
    parsed = json.loads(block)
    expected = snapshot_as_json(snapshot)
    assert parsed == expected
    assert [field(n, "id") for n in field(snapshot, "nodes")] == ["comp-foo"]

    assert re.search(r'<[A-Za-z][A-Za-z0-9]*\b[^>]*\bdata-node-id="comp-foo"', html), (
        "no node element with data-node-id=\"comp-foo\""
    )

    app_js_path = Path(provenance_tracker_ui.__file__).parent / "static" / "app.js"
    app_js = app_js_path.read_text(encoding="utf-8")
    assert app_js in html, "static/app.js is not inlined verbatim"
    rest = html.replace(app_js, "", 1)

    assert "fetch(" not in rest
    assert "XMLHttpRequest" not in rest
    assert "WebAssembly" not in rest

    attr_re = re.compile(r'\b(src|href)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', re.IGNORECASE)
    for tag in re.findall(r"<[A-Za-z][^>]*>", rest):
        for m in attr_re.finditer(tag):
            value = m.group(2) if m.group(2) is not None else (
                m.group(3) if m.group(3) is not None else m.group(4)
            )
            assert not is_external(value), "external reference found: " + tag


def test_snapshot_survives_script_close_in_reasons(tmp_path):
    reason = "comp-foo: odd </script><script>alert(1)</script> reason"
    out_dir, snapshot = run_render(tmp_path, make_report(False, [reason]))

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    block = extract_snapshot_block(html)
    parsed = json.loads(block)
    expected = snapshot_as_json(snapshot)
    assert parsed == expected
    assert parsed["not_ready_reasons"] == [reason]