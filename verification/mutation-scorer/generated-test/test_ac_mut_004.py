# hotdocs-criterion: sha256:2e7757097fdf2297ca95f046a65ca243903fbe22b869f82cb27add531230e9b4
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


def _load_run_environment():
    path = (
        Path(mutation_scorer.__file__).resolve().parents[1]
        / "run-environment"
        / "run_environment.py"
    )
    return load_module(path, "run_environment")


def _write_repo(repo_root):
    comp_dir = repo_root / "specs" / "components" / "qux"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        + "id: comp-qux\n"
        + "title: Qux\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "sealed: true\n"
        + "source_path: legacy/qux/\n"
        + "---\n"
        + "\n"
        + "# Qux\n"
    )
    code_dir = repo_root / "gen" / "qux"
    code_dir.mkdir(parents=True)
    (code_dir / "qux.py").write_text(
        "def qux():\n"
        + "    return 2 * 2\n"
    )


def _write_tests(tests_dir):
    tests_dir.mkdir(parents=True)
    first = tests_dir / "test_qux_first.py"
    first.write_text(
        "import qux\n"
        + "\n"
        + "\n"
        + "def test_qux_value():\n"
        + "    assert qux.qux() == " + repr(4) + "\n"
    )
    second = tests_dir / "test_qux_second.py"
    second.write_text(
        "from pathlib import Path\n"
        + "\n"
        + "import qux\n"
        + "\n"
        + "\n"
        + "def test_qux_value_and_cwd():\n"
        + "    assert qux.qux() == " + repr(4) + "\n"
        + "    assert (Path.cwd() / " + repr("specs") + ").is_dir()\n"
    )
    return first, second


def _score(repo_root, tests):
    run_environment = _load_run_environment()
    environment = run_environment.prepare("comp-qux", repo_root)
    try:
        assert field(environment, "ok") is True
        return mutation_scorer.score("comp-qux", repo_root, tests, environment)
    finally:
        environment.close()


def test_ac_mut_004_faulty_test_dropped_then_scored(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_repo(repo_root)
    first, second = _write_tests(tmp_path / "tests")

    result = _score(repo_root, [str(first), str(second)])

    assert [str(p) for p in field(result, "faulty_tests")] == [str(second)]
    assert field(result, "mutation_error") is None
    assert field(result, "mutation_score") == 1.0


def test_ac_mut_004_only_faulty_test_leaves_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_repo(repo_root)
    _first, second = _write_tests(tmp_path / "tests")

    result = _score(repo_root, [str(second)])

    assert [str(p) for p in field(result, "faulty_tests")] == [str(second)]
    assert field(result, "mutation_score") is None
    assert field(result, "mutation_error") is None