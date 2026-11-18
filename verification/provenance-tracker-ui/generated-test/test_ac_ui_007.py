# hotdocs-criterion: sha256:82f13f0f4764d063f0f5237eb3f5925c4ff60fb41ceba4f329f2d58eedc784b9
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
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _component_result():\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'verification_report': {\n"
        "            'component_id': 'comp-foo',\n"
        "            'criteria': [],\n"
        "            'requirement_results': {},\n"
        "            'interface_drift': False,\n"
        "            'mutation_score': None,\n"
        "            'mutation_error': None,\n"
        "            'overall': 'pass',\n"
        "        },\n"
        "        'license_scan': {'blocked': False},\n"
        "        'secret_scan': {'flagged': False},\n"
        "    }\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    logged = list(changed_ids) if changed_ids is not None else None\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(logged) + '\\n')\n"
        "    scope = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return {\n"
        "        'scope': scope,\n"
        "        'ready': True,\n"
        "        'components': {'comp-foo': _component_result()},\n"
        "        'capabilities': {},\n"
        "        'not_ready_reasons': [],\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["test-team"],
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


def test_each_build_calls_check_readiness_afresh_with_its_own_scope(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    out_first = tmp_path / "out_first"
    out_second = tmp_path / "out_second"

    snap1 = provenance_tracker_ui.render_tracker_ui(
        out_first, repo_root, changed_ids=["comp-foo"]
    )
    first_html = (out_first / "index.html").read_text(encoding="utf-8")

    snap2 = provenance_tracker_ui.render_tracker_ui(out_second, repo_root)
    second_html = (out_second / "index.html").read_text(encoding="utf-8")

    assert log_path.is_file(), "fake check_readiness was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2, lines
    assert json.loads(lines[0]) == ["comp-foo"]
    assert json.loads(lines[1]) is None

    assert "blast-radius" in first_html
    assert "comp-foo" in first_html
    assert "whole-corpus" in second_html

    assert field(snap1, "scope") == "blast-radius"
    assert list(field(snap1, "changed_ids")) == ["comp-foo"]
    assert field(snap2, "scope") == "whole-corpus"
    assert field(snap2, "changed_ids") is None