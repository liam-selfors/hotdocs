# hotdocs-criterion: sha256:3bfb0b4724c2abf126c84a59bff8b89c15aa0f80c6aeb5fb92122aa94d1c67ed
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fixture(repo_root, log_path):
    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
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
                "documents": {"component.md": "Foo component."},
            }
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (verification_dir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "covers": "R-FOO-001",
                            "kind": "compiled",
                            "result": "pass",
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": None,
                    "mutation_error": None,
                    "assets": [],
                    "overall": "pass",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('check_readiness\\n')\n"
        "    return json.loads(json.dumps(REPORT))\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('last_requirement_failures\\n')\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


def test_index_html_needs_no_server(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fixture(repo_root, log_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").splitlines().count("check_readiness") == 1
    ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert ids == ["comp-foo"]

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "http://" not in html
    assert "https://" not in html


def test_module_exposes_no_serve_function():
    assert not hasattr(provenance_tracker_ui, "serve")
    for name in dir(provenance_tracker_ui):
        if name.startswith("_"):
            continue
        obj = getattr(provenance_tracker_ui, name)
        if callable(obj):
            assert not name.lower().startswith("serve"), name


def test_main_serve_subcommand_is_usage_error(tmp_path, capsys):
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "usage error" in captured.err
    assert "Traceback" not in captured.err

    rc2 = provenance_tracker_ui.main(
        ["track", "ui", "serve", "--repo-root=" + str(tmp_path)]
    )
    assert rc2 == 2
    captured2 = capsys.readouterr()
    assert "usage error" in captured2.err
    assert "Traceback" not in captured2.err
    assert not (tmp_path / ".hotdocs" / "ui" / "index.html").exists()