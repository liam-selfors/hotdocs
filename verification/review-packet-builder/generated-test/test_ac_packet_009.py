# hotdocs-criterion: sha256:f8d96729b2d0a055628f17db58653de02d801ca3fa539017fbf2b7382bd5852c
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, req_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac_id, "covers": req_id, "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {req_id: "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }


def _license_scan(blocked):
    return {"blocked": blocked, "findings": [] if not blocked else [{"license": "GPL-3.0"}]}


def _secret_scan(flagged):
    return {"flagged": flagged, "findings": []}


def _hit(component_id, req_id, ac_id, license_blocked=False, secret_flagged=False):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, req_id, ac_id),
        "license_scan": _license_scan(license_blocked),
        "secret_scan": _secret_scan(secret_flagged),
    }


def _write_component(repo_root, slug, req_id, ac_id):
    base = repo_root / "specs" / "components" / slug
    (base / "requirements").mkdir(parents=True, exist_ok=True)
    (base / "acceptance").mkdir(parents=True, exist_ok=True)
    (base / "interface").mkdir(parents=True, exist_ok=True)
    (base / "component.md").write_text(
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " component\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n\n"
        "# " + slug + "\n\nA fixture component.\n"
    )
    (base / "requirements" / (req_id + ".md")).write_text(
        "**" + req_id + "** — The component MUST do its job.\n"
    )
    (base / "acceptance" / (ac_id + ".md")).write_text(
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: generated-test\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n"
    )
    (base / "interface" / "library.md").write_text(
        "# Library\n\n```\ndo_job() -> None\n```\n"
    )


def _write_fake_tracker(repo_root, report, log_path):
    path = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness ' + repr(changed_ids) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('last_requirement_failures ' + repr(component_id) + '\\n')\n"
        "    return []\n"
    )
    path.write_text(source)


def _git_env():
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "fixture"
    env["GIT_AUTHOR_EMAIL"] = "fixture@example.invalid"
    env["GIT_COMMITTER_NAME"] = "fixture"
    env["GIT_COMMITTER_EMAIL"] = "fixture@example.invalid"
    return env


def _git(repo_root, *args):
    subprocess.run(
        ["git", *args], cwd=str(repo_root), env=_git_env(), check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def _require_git():
    if shutil.which("git") is None:
        pytest.skip("git not available")


def _isolate_git(monkeypatch, repo_root):
    # Prevent git from discovering any enclosing repository above repo_root.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(repo_root.parent))
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)


def _assert_exemption_changes_empty(exemption_changes):
    if isinstance(exemption_changes, dict) and not exemption_changes:
        return
    assert list(field(exemption_changes, "sealed")) == []
    assert list(field(exemption_changes, "pinned_overrides")) == []


def _read_log(log_path):
    return log_path.read_text().splitlines() if log_path.exists() else []


def test_clean_merge_still_produces_packet(tmp_path, monkeypatch):
    _require_git()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _isolate_git(monkeypatch, repo_root)
    log_path = tmp_path / "calls.log"

    _write_component(repo_root, "foo", "R-FOO-001", "AC-FOO-001")
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {"comp-foo": _hit("comp-foo", "R-FOO-001", "AC-FOO-001")},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _write_fake_tracker(repo_root, report, log_path)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    changed = ["comp-foo", "R-FOO-001", "AC-FOO-001"]
    packet = review_packet_builder.build_review_packet(changed, repo_root)

    assert packet is not None
    assert any(line.startswith("check_readiness") for line in _read_log(log_path))

    assert list(field(packet, "changed_requirements")) == ["R-FOO-001"]
    assert list(field(packet, "regenerated_components")) == ["comp-foo"]
    flags = field(packet, "compliance_flags")
    assert list(field(flags, "license_scan")) == []
    assert list(field(flags, "secret_scan")) == []
    assert dict(field(packet, "provenance_hit_status")) == {"comp-foo": True}
    results = field(packet, "verification_results")
    assert "comp-foo" in results
    assert field(results["comp-foo"], "overall") == "pass"
    assert dict(field(packet, "capability_scenarios")) == {}
    # Remaining fields exist on the packet.
    field(packet, "spec_diff")
    field(packet, "exemption_changes")
    field(packet, "residual_risk")


def test_zero_commit_repo_still_produces_packet(tmp_path, monkeypatch):
    _require_git()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _isolate_git(monkeypatch, repo_root)
    log_path = tmp_path / "calls.log"

    _write_component(repo_root, "foo", "R-FOO-001", "AC-FOO-001")
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {"comp-foo": _hit("comp-foo", "R-FOO-001", "AC-FOO-001")},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _write_fake_tracker(repo_root, report, log_path)

    _git(repo_root, "init", "-q")

    changed = ["comp-foo", "R-FOO-001", "AC-FOO-001"]
    packet = review_packet_builder.build_review_packet(changed, repo_root)

    assert packet is not None
    assert not field(packet, "spec_diff")
    _assert_exemption_changes_empty(field(packet, "exemption_changes"))
    assert list(field(packet, "regenerated_components")) == ["comp-foo"]
    assert dict(field(packet, "provenance_hit_status")) == {"comp-foo": True}


def test_non_git_repo_root_still_produces_full_packet(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _isolate_git(monkeypatch, repo_root)
    log_path = tmp_path / "calls.log"
    assert not (repo_root / ".git").exists()

    _write_component(repo_root, "foo", "R-FOO-001", "AC-FOO-001")
    _write_component(repo_root, "bar", "R-BAR-001", "AC-BAR-001")

    foo_result = _hit("comp-foo", "R-FOO-001", "AC-FOO-001")
    bar_result = _hit("comp-bar", "R-BAR-001", "AC-BAR-001", license_blocked=True)
    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {"comp-foo": foo_result, "comp-bar": bar_result},
        "capabilities": {},
        "not_ready_reasons": ["comp-bar: license scan blocked"],
    }
    _write_fake_tracker(repo_root, report, log_path)

    changed = [
        "comp-foo", "R-FOO-001", "AC-FOO-001",
        "comp-bar", "R-BAR-001", "AC-BAR-001",
    ]
    packet = review_packet_builder.build_review_packet(changed, repo_root)

    assert packet is not None
    assert any(line.startswith("check_readiness") for line in _read_log(log_path))

    assert not field(packet, "spec_diff")
    _assert_exemption_changes_empty(field(packet, "exemption_changes"))

    assert sorted(field(packet, "changed_requirements")) == ["R-BAR-001", "R-FOO-001"]
    assert sorted(field(packet, "regenerated_components")) == ["comp-bar", "comp-foo"]

    results = field(packet, "verification_results")
    assert results["comp-foo"] == foo_result["verification_report"]
    assert results["comp-bar"] == bar_result["verification_report"]

    flags = field(packet, "compliance_flags")
    license_entries = list(field(flags, "license_scan"))
    assert len(license_entries) == 1
    assert field(license_entries[0], "component_id") == "comp-bar"
    assert field(license_entries[0], "result") == bar_result["license_scan"]
    assert list(field(flags, "secret_scan")) == []

    assert dict(field(packet, "provenance_hit_status")) == {
        "comp-foo": True,
        "comp-bar": True,
    }
    assert dict(field(packet, "capability_scenarios")) == {}