# hotdocs-criterion: sha256:219bca258216fb66fe2dba770310302ea0c4ce73c4ee0b78c2b4ac64f87793d4
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
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

VERIFY_REPORT = {
    "scope": "whole-corpus",
    "ready": True,
    "components": {
        "comp-foo": {
            "hit": True,
            "reason": None,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": {"blocked": False},
            "secret_scan": {"flagged": False},
        }
    },
    "capabilities": {},
    "not_ready_reasons": [],
}


def write_fake_tracker(repo_root, log_path):
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT_JSON = " + repr(json.dumps(VERIFY_REPORT)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(REPORT_JSON)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
    )
    (d / "provenance_tracker.py").write_text(src, encoding="utf-8")


def write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": VERIFICATION_REPORT,
                "provenance": {},
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
    data = json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    (v / "corpus-graph.json").write_bytes(data.encode("utf-8"))


def test_ac_ui_011_single_inlined_module_script(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    log_path = tmp_path / "fake_calls.log"

    write_fake_tracker(repo_root, log_path)
    write_corpus_graph(repo_root)

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    html = (out_dir / "index.html").read_bytes().decode("utf-8")

    asset_path = Path(provenance_tracker_ui.__file__).parent / "static" / "app.js"
    asset_text = asset_path.read_bytes().decode("utf-8")
    assert asset_text != ""

    opening = '<script type="module">'
    assert html.count(opening) == 1
    assert html.lower().count("<script") == 2
    assert '<script type="application/json" id="tracker-snapshot">' in html

    start = html.index(opening) + len(opening)
    expected = asset_text + "\ninit(document);\n"
    end = html.find("</script>", start + len(asset_text))
    assert end != -1
    assert html[start:end] == expected

    assert html.count(asset_text) == 1