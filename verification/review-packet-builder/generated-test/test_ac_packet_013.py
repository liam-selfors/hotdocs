# hotdocs-criterion: sha256:9d25e83c601f12f3a5b585e88481304212944d9cc13248e4ce7011f2f5d36304
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

import review_packet_builder


# Read once, at import, from the normally imported module's own file.
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
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]
        + list(args),
        cwd=str(repo),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_repo(repo):
    repo.mkdir(parents=True)
    _git(repo, "init")
    (repo / "README.md").write_text("fixture repo\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")


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
        "overall": "pass",
    }


def _hit_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-tool": {
                "hit": True,
                "verification_report": _verification_report("comp-tool"),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _miss_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-tool": {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            }
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-tool: no provenance for current spec state — run hotdocs generate comp-tool"
        ],
    }


def _write_tracker(path, log_path, tag, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "import copy\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "TAG = " + repr(tag) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(TAG + '\\n')\n"
        "    result = copy.deepcopy(REPORT)\n"
        "    result['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return result\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    path.write_text(src)


@pytest.fixture
def preserved_modules():
    names = ["review_packet_builder", "provenance_tracker"]
    saved = {n: sys.modules.get(n) for n in names}
    yield
    for n, m in saved.items():
        if m is None:
            sys.modules.pop(n, None)
        else:
            sys.modules[n] = m


def _setup_tool_root(tmp_path, log_path):
    t = tmp_path / "toolroot"
    copy_path = t / "gen" / "review-packet-builder" / "review_packet_builder.py"
    copy_path.parent.mkdir(parents=True)
    copy_path.write_bytes(_SOURCE_BYTES)
    _write_tracker(
        t / "gen" / "provenance-tracker" / "provenance_tracker.py",
        log_path,
        "tool",
        _hit_report(),
    )
    return t, copy_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line]


def test_tool_root_tracker_used_when_repo_has_no_gen(tmp_path, preserved_modules):
    log_path = tmp_path / "calls.log"
    t, copy_path = _setup_tool_root(tmp_path, log_path)
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    assert not (repo_root / "gen").exists()

    sys.modules.pop("provenance_tracker", None)
    module = load_module(str(copy_path), "review_packet_builder")
    packet = module.build_review_packet(["comp-tool"], repo_root)

    status = field(packet, "provenance_hit_status")
    assert dict(status) == {"comp-tool": True}
    calls = _read_log(log_path)
    assert "tool" in calls
    assert "repo" not in calls


def test_repo_root_tracker_preferred_when_present(tmp_path, preserved_modules):
    log_path = tmp_path / "calls.log"
    t, copy_path = _setup_tool_root(tmp_path, log_path)
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    _write_tracker(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        log_path,
        "repo",
        _miss_report(),
    )

    sys.modules.pop("provenance_tracker", None)
    module = load_module(str(copy_path), "review_packet_builder")
    packet = module.build_review_packet(["comp-tool"], repo_root)

    status = field(packet, "provenance_hit_status")
    assert dict(status) == {"comp-tool": False}
    calls = _read_log(log_path)
    assert "repo" in calls
    assert "tool" not in calls