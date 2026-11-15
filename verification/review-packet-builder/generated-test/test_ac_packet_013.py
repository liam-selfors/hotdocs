import importlib.util
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

import review_packet_builder


# Read the component's own source exactly once, at test-module import time,
# from the normally imported module's __file__ (never from a copy).
_SOURCE_BYTES = Path(review_packet_builder.__file__).read_bytes()


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


_TRACKER_TEMPLATE = '''\
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    hit = __HIT__
    if hit:
        component_result = {
            "hit": True,
            "verification_report": {
                "component_id": "comp-tool",
                "criteria": [
                    {"id": "AC-TOOL-001", "covers": "R-TOOL-001", "kind": "compiled", "result": "pass"}
                ],
                "requirement_results": {"R-TOOL-001": "pass"},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            },
            "license_scan": {"blocked": False, "findings": []},
            "secret_scan": {"flagged": False, "findings": []},
        }
        ready = True
        reasons = []
    else:
        component_result = {
            "hit": False,
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
        }
        ready = False
        reasons = ["comp-tool: no provenance for current spec state - run hotdocs generate comp-tool"]
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": ready,
        "components": {"comp-tool": component_result},
        "capabilities": {},
        "not_ready_reasons": reasons,
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def _write_tracker(directory: Path, hit: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    source = _TRACKER_TEMPLATE.replace("__HIT__", "True" if hit else "False")
    (directory / "provenance_tracker.py").write_text(source, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo),
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("fixture repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")


def _make_tool_root(tool_root: Path) -> Path:
    copy_dir = tool_root / "gen" / "review-packet-builder"
    copy_dir.mkdir(parents=True, exist_ok=True)
    copy_path = copy_dir / "review_packet_builder.py"
    copy_path.write_bytes(_SOURCE_BYTES)
    _write_tracker(tool_root / "gen" / "provenance-tracker", hit=True)
    return copy_path


def _load_copy(path: Path):
    module_name = "review_packet_builder_copy_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module, module_name


@pytest.fixture
def setup(tmp_path):
    tool_root = tmp_path / "tool"
    copy_path = _make_tool_root(tool_root)
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    loaded = []
    yield tool_root, copy_path, repo_root, loaded
    for name in loaded:
        sys.modules.pop(name, None)


def test_provenance_tracker_from_tool_root_when_repo_has_no_gen(setup):
    tool_root, copy_path, repo_root, loaded = setup
    assert not (repo_root / "gen").exists()

    module, name = _load_copy(copy_path)
    loaded.append(name)

    packet = module.build_review_packet(["comp-tool"], repo_root)
    status = field(packet, "provenance_hit_status")
    assert dict(status) == {"comp-tool": True}
    assert status["comp-tool"] is True


def test_provenance_tracker_from_repo_root_when_present(setup):
    tool_root, copy_path, repo_root, loaded = setup
    _write_tracker(repo_root / "gen" / "provenance-tracker", hit=False)

    module, name = _load_copy(copy_path)
    loaded.append(name)

    packet = module.build_review_packet(["comp-tool"], repo_root)
    status = field(packet, "provenance_hit_status")
    assert dict(status) == {"comp-tool": False}
    assert status["comp-tool"] is False