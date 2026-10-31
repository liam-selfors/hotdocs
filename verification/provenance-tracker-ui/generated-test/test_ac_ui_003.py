import json
import re

import provenance_tracker_ui as target


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_PROVENANCE_TRACKER_TEMPLATE = '''from pathlib import Path

CALL_LOG = Path(r"__CALL_LOG_PATH__")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with CALL_LOG.open("a", encoding="utf-8") as fh:
        fh.write("check_readiness\\n")
    scope = "blast-radius" if changed_ids else "whole-corpus"
    return {
        "scope": scope,
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {"overall": "fail"},
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-foo: no provenance for current spec state - run hotdocs generate comp-foo"
        ],
    }


def last_requirement_failures(component_id, repo_root):
    with CALL_LOG.open("a", encoding="utf-8") as fh:
        fh.write("last_requirement_failures:" + str(component_id) + "\\n")
    return ["R-FOO-002"]
'''


def _write_fake_provenance_tracker(repo_root, call_log_path):
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    source = FAKE_PROVENANCE_TRACKER_TEMPLATE.replace(
        "__CALL_LOG_PATH__", str(call_log_path)
    )
    (dep_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


def _write_corpus_graph(repo_root):
    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    corpus_graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
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
        json.dumps(corpus_graph), encoding="utf-8"
    )


def test_ac_ui_003_no_generate_action_surfaces_for_failing_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    call_log_path = tmp_path / "call_log.txt"

    _write_corpus_graph(repo_root)
    _write_fake_provenance_tracker(repo_root, call_log_path)

    snapshot = target.render_tracker_ui(
        out_dir=out_dir,
        repo_root=repo_root,
        changed_ids=None,
        model="fake-model",
        seed=0,
        llm_backend=None,
    )

    # Confirm the fake dependency actually ran, so the assertions below
    # exercise the real failing+retry_feedback scenario, not a no-op.
    assert call_log_path.exists()
    log_contents = call_log_path.read_text(encoding="utf-8")
    assert "check_readiness" in log_contents
    assert "last_requirement_failures:comp-foo" in log_contents

    nodes = _get(snapshot, "nodes")
    comp_foo_node = next(n for n in nodes if _get(n, "id") == "comp-foo")
    assert _get(comp_foo_node, "status") == "failing"
    retry_feedback = _get(comp_foo_node, "retry_feedback")
    assert retry_feedback == ["R-FOO-002"]

    index_html_path = out_dir / "index.html"
    assert index_html_path.exists()
    html = index_html_path.read_text(encoding="utf-8")

    # No <form> anywhere on the page.
    assert re.search(r"<form\b", html, re.IGNORECASE) is None

    # No href attribute other than ones beginning with "#".
    for href_value in re.findall(
        r'href\s*=\s*["\']([^"\']*)["\']', html, re.IGNORECASE
    ):
        assert href_value.startswith("#"), f"href leaves the page: {href_value!r}"

    # Every <script> except the tracker-snapshot JSON data block must not
    # contain the literal recovery command as executable script text.
    found_snapshot_block = False
    for attrs, body in re.findall(
        r"<script\b([^>]*)>(.*?)</script>", html, re.IGNORECASE | re.DOTALL
    ):
        is_snapshot_block = (
            re.search(r'id\s*=\s*["\']tracker-snapshot["\']', attrs, re.IGNORECASE)
            is not None
        )
        if is_snapshot_block:
            found_snapshot_block = True
            parsed = json.loads(body)
            reasons = _get(parsed, "not_ready_reasons")
            assert reasons
            assert any("hotdocs generate" in reason for reason in reasons)
            continue
        assert "hotdocs generate" not in body.lower()

    assert found_snapshot_block, "expected a script#tracker-snapshot JSON data block"