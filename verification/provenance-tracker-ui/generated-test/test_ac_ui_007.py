# hotdocs-criterion: sha256:11ec0780acd67ce80c22f4d53d34dc6f9797b07e44cad9d845e7bf3566748793
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _passing_result(component_id):\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'reason': None,\n"
        "        'verification_report': {\n"
        "            'component_id': component_id,\n"
        "            'criteria': [],\n"
        "            'requirement_results': {},\n"
        "            'interface_drift': False,\n"
        "            'mutation_score': None,\n"
        "            'mutation_error': None,\n"
        "            'assets': [],\n"
        "            'overall': 'pass',\n"
        "        },\n"
        "        'license_scan': {'blocked': False},\n"
        "        'secret_scan': {'flagged': False},\n"
        "    }\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(changed_ids) + '\\n')\n"
        "    scope = 'blast-radius' if changed_ids else 'whole-corpus'\n"
        "    return {\n"
        "        'scope': scope,\n"
        "        'ready': True,\n"
        "        'components': {'comp-bar': _passing_result('comp-bar')},\n"
        "        'capabilities': {},\n"
        "        'not_ready_reasons': [],\n"
        "    }\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-bar": {
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


def test_each_build_calls_check_readiness_afresh_and_states_scope(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    snap1 = provenance_tracker_ui.render_tracker_ui(
        out1, repo_root, changed_ids=["comp-foo"]
    )
    snap2 = provenance_tracker_ui.render_tracker_ui(out2, repo_root)

    lines = [
        line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(lines) == 2
    assert json.loads(lines[0]) == ["comp-foo"]
    assert json.loads(lines[1]) is None

    page1 = (out1 / "index.html").read_text(encoding="utf-8")
    page2 = (out2 / "index.html").read_text(encoding="utf-8")

    assert "blast-radius" in page1
    assert "comp-foo" in page1
    assert "whole-corpus" in page2

    assert field(snap1, "scope") == "blast-radius"
    assert field(snap1, "changed_ids") == ["comp-foo"]
    assert field(snap2, "scope") == "whole-corpus"
    assert field(snap2, "changed_ids") is None