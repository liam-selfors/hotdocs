# hotdocs-criterion: sha256:2af8a0aa7465fa8bbc71c468f8f2ddd0dd8706dbfbfb407f76b57c80c22c02a5
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import decision_drift_detector


GIT_CFG = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    subprocess.run(
        ["git"] + GIT_CFG + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


VIEW_SQL = [
    "CREATE OR REPLACE VIEW nodes AS SELECT "
    "CAST(NULL AS TEXT) AS id, CAST(NULL AS TEXT) AS title, "
    "CAST(NULL AS TEXT) AS status, CAST(NULL AS TEXT) AS kind, "
    "CAST(NULL AS TEXT) AS owner_component_id WHERE 1 = 0",
    "CREATE OR REPLACE VIEW edges AS SELECT "
    "CAST(NULL AS TEXT) AS source_id, CAST(NULL AS TEXT) AS target_id, "
    "CAST(NULL AS TEXT) AS edge_type WHERE 1 = 0",
    "CREATE OR REPLACE VIEW component_docs AS SELECT "
    "CAST(NULL AS TEXT) AS id, CAST(NULL AS TEXT) AS title, "
    "CAST(NULL AS TEXT) AS status, CAST(NULL AS TEXT) AS body WHERE 1 = 0",
    "CREATE OR REPLACE VIEW component_context AS SELECT "
    "CAST(NULL AS TEXT) AS component_id, CAST(NULL AS TEXT) AS purpose WHERE 1 = 0",
    "CREATE OR REPLACE VIEW component_provenance AS SELECT "
    "CAST(NULL AS TEXT) AS component_id, CAST(NULL AS TEXT) AS spec_bundle_hash, "
    "CAST(NULL AS STRUCT(result TEXT)) AS verification_report, "
    "CAST(NULL AS STRUCT(result TEXT)) AS license_scan, "
    "CAST(NULL AS STRUCT(result TEXT)) AS secret_scan, "
    "CAST(NULL AS BOOLEAN) AS provenance_hit WHERE 1 = 0",
    "CREATE OR REPLACE VIEW component_size AS SELECT "
    "CAST(NULL AS TEXT) AS component_id, CAST(NULL AS BIGINT) AS word_count WHERE 1 = 0",
    "CREATE OR REPLACE VIEW decision_lineage AS SELECT "
    "CAST(NULL AS TEXT) AS id, CAST(NULL AS TEXT) AS last_ratified_commit WHERE 1 = 0",
]


def build_fake_source(log_path):
    return (
        "import os\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "VIEW_SQL = " + repr(VIEW_SQL) + "\n"
        "\n"
        "\n"
        "def load_views(con, repo_root):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(str(repo_root) + '\\t' + os.path.abspath(__file__) + '\\n')\n"
        "    for sql in VIEW_SQL:\n"
        "        con.execute(sql)\n"
        "    return None\n"
    )


def test_ac_drift_006_graph_query_engine_falls_back_to_tool_root(tmp_path):
    # Locate the real component's own directory under its gen/.
    real_file = Path(decision_drift_detector.__file__).resolve()
    real_gen = next(p for p in real_file.parents if p.name == "gen")
    rel = real_file.relative_to(real_gen)
    real_comp_dir = real_gen / rel.parts[0]
    rel_in_comp = real_file.relative_to(real_comp_dir)

    # Tool root with a copy of this component and a package-shaped fake.
    tool = tmp_path / "tool"
    copy_dir = tool / "gen" / "decision-drift-detector"
    shutil.copytree(
        str(real_comp_dir),
        str(copy_dir),
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    copy_file = copy_dir / rel_in_comp

    log_path = tmp_path / "load_views.log"
    fake_pkg = tool / "gen" / "graph-query-engine" / "graph_query_engine"
    fake_pkg.mkdir(parents=True)
    fake_init = fake_pkg / "__init__.py"
    fake_init.write_text(build_fake_source(log_path))

    # repo_root with specs/ but no gen/.
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    (repo_root / "specs" / "decisions" / "D1.md").write_text(
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D1\n"
    )
    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")
    assert not (repo_root / "gen").exists()

    saved_modules = dict(sys.modules)
    try:
        copied = load_module(str(copy_file), "decision_drift_detector")
        assert Path(copied.__file__).resolve() == copy_file.resolve()
        report = copied.find_decision_drift(repo_root)
        entries = field(report, "entries")
        assert isinstance(entries, list)
    finally:
        for key in list(sys.modules):
            if key not in saved_modules:
                del sys.modules[key]
        sys.modules.update(saved_modules)

    assert log_path.is_file(), "fake load_views was never called"
    lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1, "expected exactly one load_views call, got: " + repr(lines)
    called_root, fake_file = lines[0].split("\t", 1)
    assert Path(called_root).resolve() == repo_root.resolve()
    assert Path(fake_file).resolve() == fake_init.resolve()