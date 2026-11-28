# hotdocs-criterion: sha256:ceb530cc5ab2cad536693734ada639d7fe63927359bea5d30a0f6c5a5a1f9058
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fake_tracker(repo_root, log_path):
    module_dir = repo_root / "gen" / "provenance-tracker"
    module_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    logged = None if changed_ids is None else list(changed_ids)\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(logged) + '\\n')\n"
        "    scope = " + repr("blast-radius") + " if changed_ids is not None else " + repr("whole-corpus") + "\n"
        "    return {\n"
        "        'scope': scope,\n"
        "        'ready': True,\n"
        "        'components': {},\n"
        "        'capabilities': {},\n"
        "        'secret_scan': None,\n"
        "        'not_ready_reasons': [],\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (module_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


def _write_corpus_graph(repo_root):
    verification = repo_root / "verification"
    verification.mkdir(parents=True, exist_ok=True)
    graph = {
        "nodes": {},
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (verification / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_ac_ui_007_each_build_calls_check_readiness_afresh_and_states_scope(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "check_readiness_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    out_first = tmp_path / "first"
    out_second = tmp_path / "second"

    first_snapshot = provenance_tracker_ui.render_tracker_ui(
        out_first, repo_root, changed_ids=["comp-foo"]
    )

    assert _read_log(log_path) == [["comp-foo"]]
    assert field(first_snapshot, "scope") == "blast-radius"
    assert field(first_snapshot, "changed_ids") == ["comp-foo"]

    first_page = browser.open(out_first / "index.html")
    first_text = first_page.find(css="body").text()
    assert "blast-radius" in first_text
    assert "comp-foo" in first_text
    assert first_page.console_errors() == []

    second_snapshot = provenance_tracker_ui.render_tracker_ui(out_second, repo_root)

    assert _read_log(log_path) == [["comp-foo"], None]
    assert field(second_snapshot, "scope") == "whole-corpus"
    assert field(second_snapshot, "changed_ids") is None

    second_page = browser.open(out_second / "index.html")
    second_text = second_page.find(css="body").text()
    assert "whole-corpus" in second_text
    assert second_page.console_errors() == []