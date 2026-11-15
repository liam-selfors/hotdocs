import json
import textwrap
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_PROVENANCE_TRACKER = textwrap.dedent(
    '''
    import json
    from pathlib import Path


    def _log(repo_root, record):
        log_path = Path(repo_root) / "fake_calls.log"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\\n")


    def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        _log(repo_root, {"fn": "check_readiness", "changed_ids": changed_ids,
                         "model": model, "seed": seed})
        return {
            "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
            "ready": False,
            "components": {
                "comp-foo": {
                    "hit": True,
                    "verification_report": {
                        "component_id": "comp-foo",
                        "criteria": [],
                        "requirement_results": {"R-FOO-001": "pass"},
                        "interface_drift": False,
                        "mutation_score": 0.9,
                        "overall": "pass",
                    },
                    "license_scan": {"blocked": False},
                    "secret_scan": {"flagged": False},
                },
                "comp-bar": {
                    "hit": False,
                    "verification_report": None,
                    "license_scan": None,
                    "secret_scan": None,
                },
                "comp-baz": {
                    "hit": False,
                    "verification_report": None,
                    "license_scan": None,
                    "secret_scan": None,
                },
            },
            "capabilities": {
                "P-ZERO-EDIT": {
                    "hit": True,
                    "capability_scenario_report": {
                        "P-ZERO-EDIT": {"overall": "pass", "scenarios": []}
                    },
                },
            },
            "not_ready_reasons": [
                "comp-bar: no provenance for current spec state - run hotdocs generate comp-bar",
                "comp-baz: no provenance for current spec state - run hotdocs generate comp-baz",
            ],
        }


    def write_attempt_record(component_id, generation_result, verification_report,
                             spec_bundle_hash, repo_root):
        raise AssertionError("write_attempt_record must not be called by the UI")


    def last_requirement_failures(component_id, repo_root):
        _log(repo_root, {"fn": "last_requirement_failures", "component_id": component_id})
        if component_id == "comp-bar":
            return ["R-BAR-002"]
        return []
    '''
)


def _build_repo(repo_root: Path) -> None:
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER, encoding="utf-8")

    def comp_node():
        return {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {},
        }

    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-bar": comp_node(),
            "comp-baz": comp_node(),
            "comp-foo": comp_node(),
        },
        "edges": [
            {"from": "comp-bar", "to": "comp-foo", "kind": "depends_on"},
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    verification = repo_root / "verification"
    verification.mkdir(parents=True)
    (verification / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-bar"
    attempts_dir.mkdir(parents=True)
    record = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": "comp-bar",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:abc123",
        "generation": {
            "component_id": "comp-bar",
            "spec_bundle_hash": "sha256:abc123",
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"bar.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification": {
            "component_id": "comp-bar",
            "criteria": [
                {"id": "AC-BAR-002", "covers": "R-BAR-002", "kind": "compiled", "result": "fail"}
            ],
            "requirement_results": {"R-BAR-001": "pass", "R-BAR-002": "fail"},
            "interface_drift": False,
            "mutation_score": 0.5,
            "overall": "fail",
        },
    }
    (attempts_dir / "2026-10-25T143201Z-a1b2c3.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )


def _assert_serverless(html: str) -> None:
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "http://" not in html
    assert "https://" not in html


def _run_main(argv):
    try:
        return provenance_tracker_ui.main(argv)
    except SystemExit as exc:
        return exc.code


def test_index_html_requires_no_server_blast_radius(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root, ["comp-foo"])
    assert snapshot is not None

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")
    assert html.strip()
    _assert_serverless(html)

    # The fake was actually used.
    log = (repo_root / "fake_calls.log").read_text(encoding="utf-8")
    assert "check_readiness" in log


def test_index_html_requires_no_server_whole_corpus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    out_dir = tmp_path / "out"

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert html.strip()
    _assert_serverless(html)


def test_module_exposes_no_serve_function():
    assert not hasattr(provenance_tracker_ui, "serve")


def test_serve_subcommand_is_usage_error(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    assert _run_main(["track", "ui", "serve"]) == 2
    assert _run_main(["track", "ui", "serve", f"--repo-root={repo_root}"]) == 2