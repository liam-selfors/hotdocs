import subprocess

import review_packet_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _run_git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, "git %s failed: %s" % (args, result.stderr)


COMPONENT_MD_V1 = """---
id: comp-widget
title: Widget
status: draft
owners: [lselfors@gmail.com]
sealed: true
source_path: legacy/widget.py
---

# Widget

Initial widget description.
"""

COMPONENT_MD_V2 = """---
id: comp-widget
title: Widget
status: draft
owners: [lselfors@gmail.com]
sealed: true
source_path: legacy/widget.py
---

# Widget

Updated widget description with a brand new sentence that was not present before.
"""

REQUIREMENT_MD = "**R-WIDGET-001** -- The widget component MUST do something widget-y.\n"

ACCEPTANCE_MD = """# AC-WIDGET-001

Covers: R-WIDGET-001

Given a widget
When it is used
Then it works
"""

FAKE_PROVENANCE_TRACKER_TEMPLATE = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(r"__LOG_PATH__", "a") as f:
        f.write("called\\n")
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-widget": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-widget",
                    "criteria": [
                        {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001",
                         "kind": "generated-test", "result": "pass"}
                    ],
                    "requirement_results": {"R-WIDGET-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass"
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False}
            }
        },
        "capabilities": {},
        "not_ready_reasons": []
    }
'''


def _write_widget_component(repo_root, content):
    comp_dir = repo_root / "specs" / "components" / "widget"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(content)
    (comp_dir / "requirements" / "R-WIDGET-001.md").write_text(REQUIREMENT_MD)
    (comp_dir / "acceptance" / "AC-WIDGET-001.md").write_text(ACCEPTANCE_MD)


def test_spec_diff_contains_actual_diff_text_for_changed_component_md(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _run_git(["init"], repo_root)
    # Pin the default branch name explicitly instead of relying on this
    # git install's own configured initial-branch default.
    _run_git(["symbolic-ref", "HEAD", "refs/heads/main"], repo_root)
    _run_git(["config", "user.email", "test@example.com"], repo_root)
    _run_git(["config", "user.name", "Test"], repo_root)

    _write_widget_component(repo_root, COMPONENT_MD_V1)
    _run_git(["add", "-A"], repo_root)
    _run_git(["commit", "-m", "initial widget"], repo_root)

    _run_git(["checkout", "-b", "feature"], repo_root)

    _write_widget_component(repo_root, COMPONENT_MD_V2)
    _run_git(["add", "-A"], repo_root)
    _run_git(["commit", "-m", "update widget component.md"], repo_root)

    log_path = tmp_path / "provenance_tracker_calls.log"
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True)
    (dep_dir / "provenance_tracker.py").write_text(
        FAKE_PROVENANCE_TRACKER_TEMPLATE.replace("__LOG_PATH__", str(log_path))
    )

    packet = review_packet_builder.build_review_packet(["comp-widget"], repo_root)

    spec_diff = _get(packet, "spec_diff")
    assert isinstance(spec_diff, str)
    assert "specs/components/widget/component.md" in spec_diff
    assert "-Initial widget description." in spec_diff
    assert (
        "+Updated widget description with a brand new sentence that was not present before."
        in spec_diff
    )

    assert log_path.exists()
    assert log_path.read_text().count("called") >= 1