# hotdocs-criterion: sha256:e589ca22374cbee8c568ead21af2acad66216208a33a4415564d3658ee12f72d
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
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    verification_report = {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criteria': [\n"
        "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'},\n"
        "        ],\n"
        "        'requirement_results': {'R-FOO-001': 'pass'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 0.92,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
        "    secret_scan = {\n"
        "        'scope': 'full',\n"
        "        'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
        "        'flagged': False,\n"
        "        'matches': [],\n"
        "        'allowed': [],\n"
        "        'unused_allowlist_entries': [],\n"
        "        'notified': False,\n"
        "        'notification_delivery_error': None,\n"
        "        'cache_hit': False,\n"
        "    }\n"
        "    license_scan = {'blocked': False, 'matches': [], 'notified': False}\n"
        "    return {\n"
        "        'scope': 'blast-radius' if changed_ids is not None else 'whole-corpus',\n"
        "        'ready': True,\n"
        "        'components': {\n"
        "            'comp-foo': {\n"
        "                'hit': True,\n"
        "                'reason': None,\n"
        "                'verification_report': verification_report,\n"
        "                'license_scan': license_scan,\n"
        "                'secret_scan': secret_scan,\n"
        "            },\n"
        "        },\n"
        "        'capabilities': {},\n"
        "        'secret_scan': secret_scan,\n"
        "        'not_ready_reasons': [],\n"
        "    }\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
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


def test_ac_ui_011_module_script_is_app_js_plus_init(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)
    out_dir = tmp_path / "out"

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").splitlines().count("check_readiness") == 1

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    module_tag = '<script type="module">'
    assert html.count(module_tag) == 1
    assert html.lower().count("<script") == 2
    assert html.count('<script type="application/json" id="tracker-snapshot">') == 1

    asset_path = Path(provenance_tracker_ui.__file__).resolve().parent / "static" / "app.js"
    asset_text = asset_path.read_text(encoding="utf-8")
    assert asset_text != ""

    start = html.index(module_tag) + len(module_tag)
    expected_body = asset_text + "\ninit(document);\n"
    assert html[start:start + len(expected_body) + len("</script>")] == expected_body + "</script>"
    end = html.index("</script>", start)
    assert html[start:end] == expected_body

    assert html.count(asset_text) == 1