# hotdocs-criterion: sha256:9eb9ff4774baa03f68b131bae2e462fbf30150aac1556917fbe6c22bd639fdbc
import importlib.util
import subprocess
import sys
from pathlib import Path

import review_packet_builder

# Read this component's own source exactly once, at import time, from the
# normally imported module's __file__ (never from a copy a test may delete).
_SOURCE_BYTES = Path(review_packet_builder.__file__).read_bytes()


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
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }


def _provenance_result(component_id, hit):
    if hit:
        return {
            "hit": True,
            "reason": None,
            "verification_report": _verification_report(component_id),
            "license_scan": {"blocked": False},
            "secret_scan": {"flagged": False},
        }
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def _write_tracker_stand_in(path, hit):
    components = {"comp-tool": _provenance_result("comp-tool", hit)}
    if hit:
        reasons = []
        ready = True
    else:
        reasons = [
            "comp-tool: no provenance for current spec state"
            " — run hotdocs generate comp-tool"
        ]
        ready = False
    source = (
        "COMPONENTS = " + repr(components) + "\n"
        "READY = " + repr(ready) + "\n"
        "REASONS = " + repr(reasons) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    scope = " + repr("blast-radius") + " if changed_ids is not None else " + repr("whole-corpus") + "\n"
        "    return {\n"
        "        " + repr("scope") + ": scope,\n"
        "        " + repr("ready") + ": READY,\n"
        "        " + repr("components") + ": COMPONENTS,\n"
        "        " + repr("capabilities") + ": {},\n"
        "        " + repr("not_ready_reasons") + ": list(REASONS),\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_repo(repo):
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("fixture repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")
    assert not (repo / "gen").exists()


def _make_tool_root(tool_root):
    copy_path = tool_root / "gen" / "review-packet-builder" / "review_packet_builder.py"
    copy_path.parent.mkdir(parents=True)
    copy_path.write_bytes(_SOURCE_BYTES)
    _write_tracker_stand_in(
        tool_root / "gen" / "provenance-tracker" / "provenance_tracker.py", hit=True
    )
    return copy_path


def _run_copy(copy_path, repo_root, monkeypatch):
    monkeypatch.delitem(sys.modules, "provenance_tracker", raising=False)
    saved = sys.modules.get("review_packet_builder")
    try:
        copy = load_module(copy_path, "review_packet_builder")
        assert Path(copy.__file__).resolve() == copy_path.resolve()
        return copy.build_review_packet(["comp-tool"], repo_root)
    finally:
        if saved is not None:
            sys.modules["review_packet_builder"] = saved
        else:
            sys.modules.pop("review_packet_builder", None)
        sys.modules.pop("provenance_tracker", None)


def test_tool_root_tracker_used_when_repo_has_no_gen(tmp_path, monkeypatch):
    tool_root = tmp_path / "tool"
    repo_root = tmp_path / "repo"
    copy_path = _make_tool_root(tool_root)
    _make_repo(repo_root)

    packet = _run_copy(copy_path, repo_root, monkeypatch)

    assert field(packet, "provenance_hit_status") == {"comp-tool": True}


def test_repo_root_tracker_preferred_when_present(tmp_path, monkeypatch):
    tool_root = tmp_path / "tool"
    repo_root = tmp_path / "repo"
    copy_path = _make_tool_root(tool_root)
    _make_repo(repo_root)
    _write_tracker_stand_in(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", hit=False
    )

    packet = _run_copy(copy_path, repo_root, monkeypatch)

    assert field(packet, "provenance_hit_status") == {"comp-tool": False}