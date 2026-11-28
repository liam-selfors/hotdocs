# hotdocs-criterion: sha256:82b8f6de87d82f978331f9d5565acf1b4cbeba4e3adb1674c97d05caebfff41c
import importlib.util
import subprocess
import sys
from pathlib import Path

import review_packet_builder

# Read once, at import time, from the normally imported module's own file.
_SOURCE_BYTES = Path(review_packet_builder.__file__).read_bytes()


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo), check=True, capture_output=True,
    )


def _make_repo(repo):
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("fixture\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")


def _verification_report():
    return {
        "component_id": "comp-tool",
        "criteria": [
            {"id": "AC-TOOL-001", "covers": "R-TOOL-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-TOOL-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


def _secret_scan_result():
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


def _license_scan_result():
    return {
        "blocked": False,
        "gate_version": "license_scanner@1.0.0",
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _verify_report(hit):
    if hit:
        component = {
            "hit": True,
            "reason": None,
            "verification_report": _verification_report(),
            "license_scan": _license_scan_result(),
            "secret_scan": _secret_scan_result(),
        }
        reasons = []
    else:
        component = {
            "hit": False,
            "reason": "no manifest",
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
        }
        reasons = ["comp-tool: no provenance for current spec state — run hotdocs generate comp-tool"]
    return {
        "scope": "blast-radius",
        "ready": bool(hit),
        "components": {"comp-tool": component},
        "capabilities": {},
        "secret_scan": _secret_scan_result(),
        "not_ready_reasons": reasons,
    }


def _write_stand_in(path, hit, log_path, tag):
    path.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write(" + repr(tag + " check_readiness\n") + ")\n"
        "    return " + repr(_verify_report(hit)) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write(" + repr(tag + " last_requirement_failures\n") + ")\n"
        "    return []\n"
    )
    path.write_text(source)


def _make_tool_root(tool_root, log_path):
    copy_path = tool_root / "gen" / "review-packet-builder" / "review_packet_builder.py"
    copy_path.parent.mkdir(parents=True)
    copy_path.write_bytes(_SOURCE_BYTES)
    _write_stand_in(
        tool_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        True, log_path, "tool",
    )
    return copy_path


def _run_copy(copy_path, module_name, repo_root):
    try:
        module = load_module(copy_path, module_name)
        return module.build_review_packet(["comp-tool"], repo_root)
    finally:
        sys.modules.pop(module_name, None)


def _log_tags(log_path):
    if not log_path.exists():
        return set()
    return {line.split(" ", 1)[0] for line in log_path.read_text().splitlines() if line.strip()}


def test_ac_packet_013_falls_back_to_tool_root(tmp_path):
    log_path = tmp_path / "calls.log"
    copy_path = _make_tool_root(tmp_path / "tool", log_path)
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    assert not (repo_root / "gen").exists()

    packet = _run_copy(copy_path, "review_packet_builder_ac_packet_013_a", repo_root)

    assert dict(field(packet, "provenance_hit_status")) == {"comp-tool": True}
    assert _log_tags(log_path) == {"tool"}


def test_ac_packet_013_prefers_repo_root_copy(tmp_path):
    log_path = tmp_path / "calls.log"
    copy_path = _make_tool_root(tmp_path / "tool", log_path)
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    _write_stand_in(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        False, log_path, "repo",
    )

    packet = _run_copy(copy_path, "review_packet_builder_ac_packet_013_b", repo_root)

    assert dict(field(packet, "provenance_hit_status")) == {"comp-tool": False}
    assert _log_tags(log_path) == {"repo"}