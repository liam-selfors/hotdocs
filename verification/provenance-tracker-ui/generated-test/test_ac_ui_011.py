# hotdocs-criterion: sha256:cb56cde00135c9017d7efb0108d9f1f0af7d500999031b645b3a58794f1c2c13
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report():
    return {
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
        "overall": "pass",
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


def _verify_report():
    return {
        "scope": "whole-corpus",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False},
                "secret_scan": _secret_scan(),
            }
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [],
    }


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import copy\n"
        "REPORT = " + repr(_verify_report()) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
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
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise RuntimeError('not used')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


def _write_corpus_graph(repo_root):
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
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def test_ac_ui_011_module_script_is_asset_plus_init(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_calls.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_bytes().decode("utf-8")

    asset_path = Path(provenance_tracker_ui.__file__).parent / "static" / "app.js"
    asset_text = asset_path.read_bytes().decode("utf-8")
    assert asset_text != ""

    module_open = '<script type="module">'
    json_open = '<script type="application/json" id="tracker-snapshot">'

    assert html.count(module_open) == 1
    assert html.count(json_open) == 1
    assert html.count("<script") == 2

    start = html.index(module_open) + len(module_open)
    end = html.index("</script>", start)
    module_text = html[start:end]
    assert module_text == asset_text + "\ninit(document);\n"

    assert html.count(asset_text) == 1