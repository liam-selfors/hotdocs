# hotdocs-criterion: sha256:890421a84cd3917754d3dfb7ee545904bdd5e153f2056adce59618a16ba7f395
import importlib.util
import sys
from pathlib import Path

import mutation_scorer


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


QUX_SOURCE = (
    "import importlib.util\n"
    "from pathlib import Path\n"
    "\n"
    "_BAZ_PATH = Path(__file__).resolve().parents[1] / \"baz\" / \"baz.py\"\n"
    "_SPEC = importlib.util.spec_from_file_location(\"baz\", _BAZ_PATH)\n"
    "baz = importlib.util.module_from_spec(_SPEC)\n"
    "_SPEC.loader.exec_module(baz)\n"
    "\n"
    "\n"
    "def qux():\n"
    "    return 2 * baz.baz()\n"
)

BAZ_SOURCE = (
    "def baz():\n"
    "    return 2\n"
)

TEST_SOURCE = (
    "import qux\n"
    "\n"
    "\n"
    "def test_qux_is_four():\n"
    "    assert qux.qux() == 4\n"
)


def make_repo(root):
    repo_root = root / "repo"
    comp_dir = repo_root / "specs" / "components" / "qux"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/qux/\n"
        "---\n"
        "\n"
        "# Qux\n"
    )
    qux_dir = repo_root / "gen" / "qux"
    qux_dir.mkdir(parents=True)
    (qux_dir / "qux.py").write_text(QUX_SOURCE)
    baz_dir = repo_root / "gen" / "baz"
    baz_dir.mkdir(parents=True)
    (baz_dir / "baz.py").write_text(BAZ_SOURCE)
    return repo_root


def load_run_environment():
    path = (
        Path(mutation_scorer.__file__).resolve().parents[1]
        / "run-environment"
        / "run_environment.py"
    )
    return load_module(path, "run_environment")


def prepare_env(repo_root):
    run_environment = load_run_environment()
    env = run_environment.prepare("comp-qux", repo_root)
    assert field(env, "ok") is True
    return env


def test_dependency_by_path_scores_one_and_copy_untouched(tmp_path):
    repo_root = make_repo(tmp_path)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_qux_value.py"
    test_file.write_text(TEST_SOURCE)

    qux_path = repo_root / "gen" / "qux" / "qux.py"
    original = qux_path.read_bytes()

    env = prepare_env(repo_root)
    try:
        result = mutation_scorer.score(
            "comp-qux", repo_root, [str(test_file.resolve())], env
        )
    finally:
        env.close()

    assert field(result, "mutation_error") is None
    assert field(result, "mutation_score") == 1.0
    assert qux_path.read_bytes() == original


def test_conftest_beside_test_is_not_used(tmp_path):
    repo_root = make_repo(tmp_path)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    qux_dir = str((repo_root / "gen" / "qux").resolve())
    (tests_dir / "conftest.py").write_text(
        "import sys\n"
        "sys.path.insert(0, " + repr(qux_dir) + ")\n"
        "import qux\n"
    )
    test_file = tests_dir / "test_qux_value.py"
    test_file.write_text(TEST_SOURCE)

    env = prepare_env(repo_root)
    try:
        result = mutation_scorer.score(
            "comp-qux", repo_root, [str(test_file.resolve())], env
        )
    finally:
        env.close()

    assert field(result, "mutation_error") is None
    assert field(result, "mutation_score") == 1.0


def test_no_tests_runs_nothing(tmp_path):
    repo_root = make_repo(tmp_path)

    env = prepare_env(repo_root)
    try:
        result = mutation_scorer.score("comp-qux", repo_root, [], env)
    finally:
        env.close()

    assert field(result, "mutation_score") is None
    assert field(result, "mutation_error") is None
    assert field(result, "mutants") == 0