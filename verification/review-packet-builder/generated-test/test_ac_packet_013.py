import importlib.util
import os
import subprocess
import sys
import uuid
from pathlib import Path

import review_packet_builder


# Read once, at import time, from the normally imported module's own file.
_SOURCE_BYTES = Path(review_packet_builder.__file__).read_bytes()


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    subprocess.run(
        [
            "git",
            "-c", "user.name=test",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            "-c", "init.defaultBranch=main",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def _make_repo(repo_root):
    repo_root.mkdir(parents=True)
    _git(repo_root, "init")
    (repo_root / "README.md").write_text("fixture repo\n")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "initial")
    assert not (repo_root / "gen").exists()


def _stand_in_source(hit, log_path):
    if hit:
        component_result = (
            "{\n"
            "        'hit': True,\n"
            "        'verification_report': {\n"
            "            'component_id': 'comp-tool',\n"
            "            'criteria': [],\n"
            "            'requirement_results': {},\n"
            "            'interface_drift': False,\n"
            "            'mutation_score': 1.0,\n"
            "            'overall': 'pass',\n"
            "        },\n"
            "        'license_scan': {'blocked': False, 'findings': []},\n"
            "        'secret_scan': {'flagged': False, 'findings': []},\n"
            "    }"
        )
        ready = "True"
        reasons = "[]"
    else:
        component_result = (
            "{\n"
            "        'hit': False,\n"
            "        'verification_report': None,\n"
            "        'license_scan': None,\n"
            "        'secret_scan': None,\n"
            "    }"
        )
        ready = "False"
        reasons = (
            "['comp-tool: no provenance for current spec state "
            "\u2014 run hotdocs generate comp-tool']"
        )
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return {\n"
        "        'scope': 'blast-radius' if changed_ids is not None else 'whole-corpus',\n"
        "        'ready': " + ready + ",\n"
        "        'components': {\n"
        "            'comp-tool': " + component_result + ",\n"
        "        },\n"
        "        'capabilities': {},\n"
        "        'not_ready_reasons': " + reasons + ",\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _write_stand_in(root, hit, log_path):
    d = root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    (d / "provenance_tracker.py").write_text(_stand_in_source(hit, log_path))


def _make_tool_root(tool_root, tool_log):
    copy_dir = tool_root / "gen" / "review-packet-builder"
    copy_dir.mkdir(parents=True)
    copy_path = copy_dir / "review_packet_builder.py"
    copy_path.write_bytes(_SOURCE_BYTES)
    _write_stand_in(tool_root, hit=True, log_path=tool_log)
    return copy_path


def _load_copy(copy_path):
    module_name = "review_packet_builder_copy_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(module_name, str(copy_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module, module_name


def _read_log(path):
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line.strip()]


def test_tool_root_provenance_tracker_used_when_repo_has_no_gen(tmp_path):
    tool_root = tmp_path / "tool"
    repo_root = tmp_path / "repo"
    tool_log = tmp_path / "tool_tracker.log"

    copy_path = _make_tool_root(tool_root, tool_log)
    _make_repo(repo_root)

    module, module_name = _load_copy(copy_path)
    try:
        packet = module.build_review_packet(["comp-tool"], repo_root)
    finally:
        sys.modules.pop(module_name, None)

    status = field(packet, "provenance_hit_status")
    assert dict(status) == {"comp-tool": True}
    assert _read_log(tool_log), "tool-root provenance-tracker stand-in was never invoked"


def test_repo_root_provenance_tracker_preferred_when_present(tmp_path):
    tool_root = tmp_path / "tool"
    repo_root = tmp_path / "repo"
    tool_log = tmp_path / "tool_tracker.log"
    repo_log = tmp_path / "repo_tracker.log"

    copy_path = _make_tool_root(tool_root, tool_log)
    _make_repo(repo_root)
    _write_stand_in(repo_root, hit=False, log_path=repo_log)

    module, module_name = _load_copy(copy_path)
    try:
        packet = module.build_review_packet(["comp-tool"], repo_root)
    finally:
        sys.modules.pop(module_name, None)

    status = field(packet, "provenance_hit_status")
    assert dict(status) == {"comp-tool": False}
    assert _read_log(repo_log), "repo_root provenance-tracker stand-in was never invoked"