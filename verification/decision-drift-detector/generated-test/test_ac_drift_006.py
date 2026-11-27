# hotdocs-criterion: sha256:7153936c6d1698b945a0124437bd7105e753e0f2318fbeeb4481f0099558db5b
"""AC-DRIFT-006: graph-query-engine falls back to the tool root.

Given a repo_root with specs/ but no gen/ directory, and a copy of this
component's code placed at <tool>/gen/decision-drift-detector/ beside a
package-shaped fake at
<tool>/gen/graph-query-engine/graph_query_engine/__init__.py that records
every load_views call, when find_decision_drift runs against that
repo_root (loaded from the copy), then the fake's load_views was called
exactly once, with that repo_root, graph-query-engine having been loaded
from the tool root.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import decision_drift_detector


MODULE_NAME = "decision_drift_detector"
GIT_CFG = [
    "-c", "user.name=t",
    "-c", "user.email=t@t",
    "-c", "commit.gpgsign=false",
]


def load_module(path, module_name, submodule_search_locations=None):
    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=submodule_search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    subprocess.run(
        ["git", *GIT_CFG, *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


def component_dir():
    """The directory directly under the nearest `gen/` holding this module."""
    here = Path(decision_drift_detector.__file__).resolve()
    for p in here.parents:
        if p.parent.name == "gen":
            return p
    raise AssertionError("component is not located under a gen/ directory")


VIEW_SQL = [
    "CREATE OR REPLACE VIEW nodes AS SELECT "
    "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
    "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS kind, "
    "CAST(NULL AS VARCHAR) AS owner_component_id WHERE FALSE",
    "CREATE OR REPLACE VIEW edges AS SELECT "
    "CAST(NULL AS VARCHAR) AS source_id, CAST(NULL AS VARCHAR) AS target_id, "
    "CAST(NULL AS VARCHAR) AS edge_type WHERE FALSE",
    "CREATE OR REPLACE VIEW component_docs AS SELECT "
    "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
    "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS body WHERE FALSE",
    "CREATE OR REPLACE VIEW component_context AS SELECT "
    "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS VARCHAR) AS purpose "
    "WHERE FALSE",
    "CREATE OR REPLACE VIEW component_provenance AS SELECT "
    "CAST(NULL AS VARCHAR) AS component_id, "
    "CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
    "CAST(NULL AS STRUCT(result VARCHAR)) AS verification_report, "
    "CAST(NULL AS STRUCT(result VARCHAR)) AS license_scan, "
    "CAST(NULL AS STRUCT(result VARCHAR)) AS secret_scan, "
    "CAST(NULL AS BOOLEAN) AS provenance_hit WHERE FALSE",
    "CREATE OR REPLACE VIEW component_size AS SELECT "
    "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS BIGINT) AS word_count "
    "WHERE FALSE",
    "CREATE OR REPLACE VIEW bundle_size AS SELECT "
    "CAST(NULL AS VARCHAR) AS component_id, "
    "CAST(NULL AS BIGINT) AS generator_words, "
    "CAST(NULL AS BIGINT) AS criterion_words_max WHERE FALSE",
    "CREATE OR REPLACE VIEW decision_lineage AS SELECT "
    "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS last_ratified_commit "
    "WHERE FALSE",
]


def fake_gqe_source(log_path):
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "_VIEW_SQL = " + repr(VIEW_SQL) + "\n"
        "\n"
        "\n"
        "def load_views(con, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(repo_root) + '\\n')\n"
        "    for sql in _VIEW_SQL:\n"
        "        con.execute(sql)\n"
        "    return None\n"
    )


def build_repo(repo_root):
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "D1.md").write_text(
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D1\n",
        encoding="utf-8",
    )
    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")


def test_ac_drift_006_graph_query_engine_loaded_from_tool_root(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)
    assert (repo_root / "specs").is_dir()
    assert not (repo_root / "gen").exists()

    tool = tmp_path / "tool"
    tool_gen = tool / "gen"
    tool_gen.mkdir(parents=True)

    # Copy this component's code into <tool>/gen/decision-drift-detector/.
    src_dir = component_dir()
    copy_dir = tool_gen / "decision-drift-detector"
    shutil.copytree(
        src_dir,
        copy_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )

    # Package-shaped fake graph-query-engine at the tool root.
    log_path = tmp_path / "load_views_calls.log"
    fake_pkg = tool_gen / "graph-query-engine" / "graph_query_engine"
    fake_pkg.mkdir(parents=True)
    (fake_pkg / "__init__.py").write_text(
        fake_gqe_source(log_path), encoding="utf-8"
    )

    flat = copy_dir / (MODULE_NAME + ".py")
    pkg_init = copy_dir / MODULE_NAME / "__init__.py"

    saved = {
        k: v
        for k, v in sys.modules.items()
        if k == MODULE_NAME
        or k.startswith(MODULE_NAME + ".")
        or k == "graph_query_engine"
        or k.startswith("graph_query_engine.")
    }
    try:
        if flat.is_file():
            copy_module = load_module(flat, MODULE_NAME)
        else:
            assert pkg_init.is_file(), "copied component has no loadable module"
            copy_module = load_module(
                pkg_init,
                MODULE_NAME,
                submodule_search_locations=[str(pkg_init.parent)],
            )
        assert Path(copy_module.__file__).resolve().is_relative_to(
            copy_dir.resolve()
        )

        report = copy_module.find_decision_drift(repo_root)
        entries = field(report, "entries")
        assert isinstance(entries, list)
    finally:
        for k in list(sys.modules):
            if (
                k == MODULE_NAME
                or k.startswith(MODULE_NAME + ".")
                or k == "graph_query_engine"
                or k.startswith("graph_query_engine.")
            ):
                del sys.modules[k]
        sys.modules.update(saved)

    assert log_path.is_file(), (
        "the tool-root fake graph-query-engine's load_views was never called"
    )
    calls = [
        line
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(calls) == 1, calls
    assert Path(calls[0]).resolve() == repo_root.resolve()