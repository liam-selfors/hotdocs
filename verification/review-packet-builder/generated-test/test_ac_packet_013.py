import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import review_packet_builder as _rpb_for_source

_REAL_MODULE_FILE = Path(_rpb_for_source.__file__).resolve()

if _REAL_MODULE_FILE.name == "__init__.py":
    _MODULE_IS_PACKAGE = True
    _PACKAGE_ROOT = _REAL_MODULE_FILE.parent
    _PACKAGE_FILE_CONTENTS = {
        p.relative_to(_PACKAGE_ROOT): p.read_bytes()
        for p in sorted(_PACKAGE_ROOT.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }
else:
    _MODULE_IS_PACKAGE = False
    _FLAT_MODULE_BYTES = _REAL_MODULE_FILE.read_bytes()


def _materialize_component_copy(dest_component_dir: Path) -> Path:
    dest_component_dir.mkdir(parents=True, exist_ok=True)
    if _MODULE_IS_PACKAGE:
        package_dir = dest_component_dir / "review_packet_builder"
        for rel, data in _PACKAGE_FILE_CONTENTS.items():
            target = package_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return package_dir / "__init__.py"
    target = dest_component_dir / "review_packet_builder.py"
    target.write_bytes(_FLAT_MODULE_BYTES)
    return target


def _load_module_by_path(module_path: Path):
    if module_path.name == "__init__.py":
        spec = importlib.util.spec_from_file_location(
            "review_packet_builder",
            module_path,
            submodule_search_locations=[str(module_path.parent)],
        )
    else:
        spec = importlib.util.spec_from_file_location("review_packet_builder", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["review_packet_builder"] = module
    spec.loader.exec_module(module)
    return module


def _write_provenance_tracker_stub(path: Path, hit: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hit:
        components = {
            "comp-tool": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-tool",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"component_id": "comp-tool", "blocked": False},
                "secret_scan": {"component_id": "comp-tool", "flagged": False},
            }
        }
        not_ready_reasons = []
    else:
        components = {
            "comp-tool": {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            }
        }
        not_ready_reasons = ["comp-tool: no provenance for current spec state"]

    report = {
        "scope": "blast-radius",
        "ready": hit,
        "components": components,
        "capabilities": {},
        "not_ready_reasons": not_ready_reasons,
    }

    source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return " + repr(report) + "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    path.write_text(source)


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, env=env)
    (path / "README.md").write_text("placeholder\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=path, check=True, capture_output=True, env=env
    )


def _read_hit_status(packet):
    return (
        packet.get("provenance_hit_status")
        if isinstance(packet, dict)
        else getattr(packet, "provenance_hit_status", None)
    )


def test_provenance_hit_status_prefers_repo_root_tracker_over_tool_root(tmp_path):
    tool_root = tmp_path / "tool_root"
    repo_root = tmp_path / "repo_root"

    component_copy_path = _materialize_component_copy(
        tool_root / "gen" / "review-packet-builder"
    )
    _write_provenance_tracker_stub(
        tool_root / "gen" / "provenance-tracker" / "provenance_tracker.py", hit=True
    )

    _init_git_repo(repo_root)
    assert not (repo_root / "gen").exists()

    loaded_module = _load_module_by_path(component_copy_path)

    try:
        packet_with_tool_root_tracker = loaded_module.build_review_packet(
            ["comp-tool"], repo_root
        )
        hit_status_from_tool_root = _read_hit_status(packet_with_tool_root_tracker)
        assert hit_status_from_tool_root == {"comp-tool": True}

        _write_provenance_tracker_stub(
            repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", hit=False
        )

        packet_with_repo_root_tracker = loaded_module.build_review_packet(
            ["comp-tool"], repo_root
        )
        hit_status_from_repo_root = _read_hit_status(packet_with_repo_root_tracker)
        assert hit_status_from_repo_root == {"comp-tool": False}
    finally:
        sys.modules["review_packet_builder"] = _rpb_for_source