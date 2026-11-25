# hotdocs-criterion: sha256:31ffe0935e8b932519bb937b73f3ccf1afdb5d5a59a0811be8bedcdea8de514f
import dataclasses
import json
import re
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def normalize(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return normalize(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return normalize(value.to_dict())
    return value


def snapshot_as_json(snapshot):
    keys = ["scope", "changed_ids", "ready", "not_ready_reasons", "nodes", "edges"]
    return {k: normalize(field(snapshot, k)) for k in keys}


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
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
    "overall": "pass",
}

SECRET_SCAN = {
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

LICENSE_SCAN = {"blocked": False, "matches": [], "gate_version": "license_scanner@1.0.0"}


def make_report(not_ready_reasons, ready):
    return {
        "scope": "whole-corpus",
        "ready": ready,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": VERIFICATION_REPORT,
                "license_scan": LICENSE_SCAN,
                "secret_scan": SECRET_SCAN,
            }
        },
        "capabilities": {},
        "secret_scan": SECRET_SCAN,
        "not_ready_reasons": not_ready_reasons,
    }


def build_repo(tmp_path, report):
    repo_root = tmp_path / "repo"
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    log_path = tmp_path / "check_readiness.log"
    src = (
        "import json\n"
        "\n"
        "_REPORT = " + repr(report) + "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return json.loads(json.dumps(_REPORT))\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")

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
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return repo_root, log_path


SNAPSHOT_RE = re.compile(
    r'<script type="application/json" id="tracker-snapshot">(.*?)</script>', re.DOTALL
)


def extract_snapshot(html):
    matches = SNAPSHOT_RE.findall(html)
    assert len(matches) == 1, "expected exactly one tracker-snapshot element"
    return json.loads(matches[0])


def is_external(value):
    v = value.strip()
    if v == "" or v.startswith("#"):
        return False
    if v.lower().startswith("data:"):
        return False
    return True


def test_single_self_contained_index_html(tmp_path):
    repo_root, log_path = build_repo(tmp_path, make_report([], True))
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.read_text(encoding="utf-8").splitlines() == ["check_readiness"]

    files = [p for p in out_dir.rglob("*") if p.is_file()]
    assert [p.relative_to(out_dir).as_posix() for p in files] == ["index.html"]
    assert [p for p in out_dir.rglob("*") if p.is_dir()] == []

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    parsed = extract_snapshot(html)
    assert parsed == snapshot_as_json(snapshot)

    assert re.search(r'<[A-Za-z][^>]*\sdata-node-id="comp-foo"', html)

    asset = Path(provenance_tracker_ui.__file__).resolve().parent / "static" / "app.js"
    asset_text = asset.read_text(encoding="utf-8")
    remaining = html.replace(asset_text, "", 1) if asset_text else html

    assert "fetch(" not in remaining
    assert "XMLHttpRequest" not in remaining
    assert "WebAssembly" not in remaining

    for m in re.finditer(r"<[A-Za-z][^>]*>", remaining):
        tag = m.group(0)
        for attr in re.finditer(
            r"""\s(?:src|href)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
            tag,
            re.IGNORECASE,
        ):
            value = next(g for g in attr.groups() if g is not None)
            assert not is_external(value), "external reference: " + tag


def test_snapshot_survives_closing_script_in_reasons(tmp_path):
    reasons = ["comp-foo: weird </script><script>alert(1)</script> reason"]
    repo_root, log_path = build_repo(tmp_path, make_report(reasons, False))
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    parsed = extract_snapshot(html)
    expected = snapshot_as_json(snapshot)
    assert parsed == expected
    assert parsed["not_ready_reasons"] == reasons