# hotdocs-criterion: sha256:689909968718528bf6fb3fcda8fb8859db4c54922de7efd1cddb49955728a2d3
import importlib.util
import subprocess
import sys
from pathlib import Path

import review_packet_builder


# Read once, at import time, from the normally imported module's own file.
_SOURCE_BYTES = Path(review_packet_builder.__file__).resolve().read_bytes()

_COUNTER = [0]


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
            {"id": "AC-TOOL-001", "covers": "R-TOOL-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-TOOL-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
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


def _license_scan():
    return {
        "blocked": False,
        "matches": [],
        "gate_version": "license_scanner@1.0.0",
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


def _write_tracker_stand_in(directory, report, log_path, tag):
    directory.mkdir(parents=True, exist_ok=True)
    source = (
        "from pathlib import Path\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "TAG = " + repr(tag) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(TAG + ':' + line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    (directory / "provenance_tracker.py").write_text(source, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "initial")
    return repo_root


def _make_tool_copy(tmp_path, log_path):
    tool_root = tmp_path / "tool"
    copy_dir = tool_root / "gen" / "review-packet-builder"
    copy_dir.mkdir(parents=True)
    copy_path = copy_dir / "review_packet_builder.py"
    copy_path.write_bytes(_SOURCE_BYTES)
    _write_tracker_stand_in(
        tool_root / "gen" / "provenance-tracker", _hit_report(), log_path, "tool"
    )
    _COUNTER[0] += 1
    module_name = "review_packet_builder_toolcopy_" + str(_COUNTER[0])
    return load_module(copy_path, module_name)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def test_tool_root_tracker_used_when_repo_has_no_gen(tmp_path):
    log_path = tmp_path / "calls.log"
    repo_root = _make_repo(tmp_path)
    assert not (repo_root / "gen").exists()
    copy = _make_tool_copy(tmp_path, log_path)

    packet = copy.build_review_packet(["comp-tool"], repo_root)

    assert field(packet, "provenance_hit_status") == {"comp-tool": True}
    lines = _read_log(log_path)
    assert any(line.startswith("tool:") for line in lines)
    assert not any(line.startswith("repo:") for line in lines)


def test_repo_root_tracker_preferred_when_present(tmp_path):
    log_path = tmp_path / "calls.log"
    repo_root = _make_repo(tmp_path)
    _write_tracker_stand_in(
        repo_root / "gen" / "provenance-tracker", _miss_report(), log_path, "repo"
    )
    copy = _make_tool_copy(tmp_path, log_path)

    packet = copy.build_review_packet(["comp-tool"], repo_root)

    assert field(packet, "provenance_hit_status") == {"comp-tool": False}
    lines = _read_log(log_path)
    assert any(line.startswith("repo:") for line in lines)
    assert not any(line.startswith("tool:") for line in lines)