# hotdocs-criterion: sha256:7e00cee7f409f547c8f76ddf36366e1cbcf082ab3fe905488787772718fe34fe
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

import decision_drift_detector


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


_FAKE_GQE_TEMPLATE = '''
import json
import os

_LOG_PATH = __LOG_PATH__

_VIEW_SQL = [
    "CREATE OR REPLACE VIEW nodes AS SELECT "
    "CAST(NULL AS VARCHAR) AS id, "
    "CAST(NULL AS VARCHAR) AS title, "
    "CAST(NULL AS VARCHAR) AS status, "
    "CAST(NULL AS VARCHAR) AS kind, "
    "CAST(NULL AS VARCHAR) AS owner_component_id LIMIT 0",
    "CREATE OR REPLACE VIEW edges AS SELECT "
    "CAST(NULL AS VARCHAR) AS source_id, "
    "CAST(NULL AS VARCHAR) AS target_id, "
    "CAST(NULL AS VARCHAR) AS edge_type LIMIT 0",
    "CREATE OR REPLACE VIEW component_docs AS SELECT "
    "CAST(NULL AS VARCHAR) AS id, "
    "CAST(NULL AS VARCHAR) AS title, "
    "CAST(NULL AS VARCHAR) AS status, "
    "CAST(NULL AS VARCHAR) AS body LIMIT 0",
    "CREATE OR REPLACE VIEW component_context AS SELECT "
    "CAST(NULL AS VARCHAR) AS component_id, "
    "CAST(NULL AS VARCHAR) AS purpose LIMIT 0",
    "CREATE OR REPLACE VIEW component_provenance AS SELECT "
    "CAST(NULL AS VARCHAR) AS component_id, "
    "CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
    "CAST(NULL AS STRUCT(status VARCHAR)) AS verification_report, "
    "CAST(NULL AS STRUCT(status VARCHAR)) AS license_scan, "
    "CAST(NULL AS STRUCT(status VARCHAR)) AS secret_scan, "
    "CAST(NULL AS BOOLEAN) AS provenance_hit LIMIT 0",
    "CREATE OR REPLACE VIEW component_size AS SELECT "
    "CAST(NULL AS VARCHAR) AS component_id, "
    "CAST(NULL AS BIGINT) AS word_count LIMIT 0",
    "CREATE OR REPLACE VIEW decision_lineage AS SELECT "
    "CAST(NULL AS VARCHAR) AS id, "
    "CAST(NULL AS VARCHAR) AS last_ratified_commit LIMIT 0",
]


def load_views(con, repo_root):
    record = {
        "repo_root": str(repo_root),
        "fake_file": os.path.abspath(__file__),
    }
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
    for sql in _VIEW_SQL:
        try:
            con.execute(sql)
        except Exception:
            pass
    return None
'''


def _write_fake_gqe_package(tool_root, log_path):
    pkg_dir = tool_root / "gen" / "graph-query-engine" / "graph_query_engine"
    pkg_dir.mkdir(parents=True)
    init_path = pkg_dir / "__init__.py"
    init_path.write_text(
        _FAKE_GQE_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path))),
        encoding="utf-8",
    )
    return init_path


def _copy_component(tool_root):
    orig_file = Path(decision_drift_detector.__file__).resolve()
    is_pkg = orig_file.name == "__init__.py"
    if is_pkg:
        module_src = orig_file.parent
        container = module_src.parent
    else:
        module_src = orig_file
        container = orig_file.parent

    dest_dir = tool_root / "gen" / "decision-drift-detector"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".git")
    if container.name == "decision-drift-detector":
        shutil.copytree(container, dest_dir, ignore=ignore)
    else:
        dest_dir.mkdir(parents=True)
        if is_pkg:
            shutil.copytree(
                module_src, dest_dir / "decision_drift_detector", ignore=ignore
            )
        else:
            shutil.copy2(module_src, dest_dir / "decision_drift_detector.py")

    if is_pkg:
        copy_path = dest_dir / "decision_drift_detector" / "__init__.py"
    else:
        copy_path = dest_dir / "decision_drift_detector.py"
    assert copy_path.is_file(), f"component copy missing at {copy_path}"
    return copy_path, is_pkg


def _write_repo(repo_root):
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    (repo_root / "specs" / "components").mkdir(parents=True)
    (decisions / "D1.md").write_text(
        "---\n"
        "id: D1\n"
        "title: Placeholder decision\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "Placeholder decision for a drift-detector fixture.\n",
        encoding="utf-8",
    )
    git = shutil.which("git")
    if git:
        env = dict(os.environ)
        env.update(
            {
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
            }
        )
        for args in (
            ["init", "-q"],
            ["add", "-A"],
            ["commit", "-q", "-m", "fixture"],
        ):
            subprocess.run(
                [git, *args],
                cwd=str(repo_root),
                env=env,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    assert not (repo_root / "gen").exists()


def _is_ours(key):
    return (
        key == "decision_drift_detector"
        or key.startswith("decision_drift_detector.")
        or key == "graph_query_engine"
        or key.startswith("graph_query_engine.")
    )


def test_ac_drift_006_gqe_resolved_from_tool_root_when_repo_has_no_gen(tmp_path):
    base = tmp_path / f"drift006_{uuid.uuid4().hex}"
    tool_root = base / "tool"
    repo_root = base / "repo"
    log_path = base / "load_views_calls.jsonl"
    tool_root.mkdir(parents=True)
    repo_root.mkdir(parents=True)

    _write_repo(repo_root)
    copy_path, is_pkg = _copy_component(tool_root)
    fake_init = _write_fake_gqe_package(tool_root, log_path)
    assert not (
        tool_root / "gen" / "graph-query-engine" / "graph_query_engine.py"
    ).exists()

    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for k in saved:
        del sys.modules[k]
    importlib.invalidate_caches()

    try:
        spec = importlib.util.spec_from_file_location(
            "decision_drift_detector",
            str(copy_path),
            submodule_search_locations=[str(copy_path.parent)] if is_pkg else None,
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["decision_drift_detector"] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)

        assert Path(module.__file__).resolve() == copy_path.resolve()

        report = module.find_decision_drift(repo_root)
    finally:
        for k in [k for k in list(sys.modules) if _is_ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)

    assert log_path.exists(), (
        "fake graph-query-engine load_views was never called; the component "
        "did not resolve graph-query-engine from the tool root"
    )
    lines = [
        ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    records = [json.loads(ln) for ln in lines]
    assert len(records) == 1, f"expected exactly one load_views call, got {records}"

    rec = records[0]
    assert Path(rec["repo_root"]).resolve() == repo_root.resolve()
    assert Path(rec["fake_file"]).resolve() == fake_init.resolve()

    entries = _field(report, "entries")
    assert entries is not None
    assert isinstance(entries, (list, tuple))