# hotdocs-criterion: sha256:a1df7121707a99ee438cdc842e79502fcf52af3edc0d198a5d40d8f4931dfc31
import importlib.util
import subprocess
import sys
from pathlib import Path

import review_packet_builder


# Read once, at import time, from the normally imported module's own file;
# never from a copy, which a test may delete.
_SOURCE_BYTES = Path(review_packet_builder.__file__).resolve().read_bytes()


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id):
    return {
        "component_id": component_id,
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


def _license_scan():
    return {
        "blocked": False,
        "gate_version": "license_scanner@1.0.0",
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan():
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


def _hit_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-tool": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-tool"),
                "license_scan": _license_scan(),
                "secret_scan": _secret_scan(),
            }
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [],
    }


def _miss_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-tool": {
                "hit": False,
                "reason": "no manifest",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            }
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-tool: no provenance for current spec state — run hotdocs generate comp-tool"
        ],
    }


def _write_tracker(path, report, log_path, label):
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "import copy\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "LABEL = " + repr(label) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(LABEL + '\\n')\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    path.write_text(src, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_repo(repo_root):
    repo_root.mkdir(parents=True)
    _git(repo_root, "init", "-q")
    (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "initial")


def _make_tool_root(tool_root, log_path):
    copy_path = tool_root / "gen" / "review-packet-builder" / "review_packet_builder.py"
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_bytes(_SOURCE_BYTES)
    _write_tracker(
        tool_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _hit_report(),
        log_path,
        "tool",
    )
    return copy_path


def _run_copy(copy_path, module_name, repo_root):
    try:
        module = load_module(copy_path, module_name)
        return module.build_review_packet(["comp-tool"], repo_root)
    finally:
        sys.modules.pop(module_name, None)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def test_tool_root_tracker_used_when_repo_has_no_gen(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = tmp_path / "tool"
    copy_path = _make_tool_root(tool_root, log_path)
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    assert not (repo_root / "gen").exists()

    packet = _run_copy(copy_path, "review_packet_builder_ac013_toolcopy_a", repo_root)

    status = field(packet, "provenance_hit_status")
    assert dict(status) == {"comp-tool": True}
    calls = _read_log(log_path)
    assert "tool" in calls
    assert "repo" not in calls


def test_repo_tracker_preferred_when_repo_gen_exists(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = tmp_path / "tool"
    copy_path = _make_tool_root(tool_root, log_path)
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    _write_tracker(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _miss_report(),
        log_path,
        "repo",
    )

    packet = _run_copy(copy_path, "review_packet_builder_ac013_toolcopy_b", repo_root)

    status = field(packet, "provenance_hit_status")
    assert dict(status) == {"comp-tool": False}
    calls = _read_log(log_path)
    assert "repo" in calls
    assert "tool" not in calls