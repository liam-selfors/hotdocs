# hotdocs-criterion: sha256:a1ffbfa433f6c918ba91755f720d99276daefc865f598ac03d0dabbb66843b00
import importlib.util
import sys
import time
from pathlib import Path

import mutation_scorer


JS = "function f(a, b) { return a === b; }" + " " * 200


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_run_environment():
    path = (
        Path(mutation_scorer.__file__).resolve().parents[1]
        / "run-environment"
        / "run_environment.py"
    )
    return load_module(path, "run_environment")


def build_repo(root, qux_source):
    repo_root = root / "repo"
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
    gen_dir = repo_root / "gen" / "qux"
    gen_dir.mkdir(parents=True)
    (gen_dir / "qux.py").write_text(qux_source)
    return repo_root


def write_test(root, body):
    tests_dir = root / "tests_outside"
    tests_dir.mkdir(parents=True, exist_ok=True)
    path = tests_dir / "test_qux_behaviour.py"
    path.write_text(body)
    return str(path.resolve())


def run_score(repo_root, tests):
    run_environment = load_run_environment()
    env = run_environment.prepare("comp-qux", repo_root)
    try:
        assert field(env, "ok") is True
        return mutation_scorer.score("comp-qux", repo_root, tests, env)
    finally:
        env.close()


SIMPLE_TEST = (
    "import qux\n"
    + "\n"
    + "\n"
    + "def test_qux():\n"
    + "    assert qux.qux() == 4\n"
)


def test_javascript_in_string_constant_ends_scoring(tmp_path):
    source = (
        '"""Doc."""\n\nSCRIPT = '
        + repr(JS)
        + "\n\n\ndef qux():\n    return 4\n"
    )
    repo_root = build_repo(tmp_path, source)
    test_file = write_test(tmp_path, SIMPLE_TEST)

    result = run_score(repo_root, [test_file])

    assert field(result, "mutation_score") is None
    assert field(result, "mutation_error") == (
        "javascript in a string at qux.py:3; declare it as an asset "
        "(specs/architecture/asset-kinds.md)"
    )


def test_javascript_in_docstring_is_not_flagged(tmp_path):
    source = repr(JS) + "\n\n\ndef qux():\n    return 4\n"
    repo_root = build_repo(tmp_path, source)
    test_file = write_test(tmp_path, SIMPLE_TEST)

    result = run_score(repo_root, [test_file])

    assert field(result, "mutation_error") is None
    assert field(result, "mutation_score") == 1.0


def test_non_terminating_mutant_times_out_and_is_killed(tmp_path):
    source = (
        "def qux(x, i):\n"
        + "    while i < x: i = i + 1\n"
        + "    return i\n"
    )
    repo_root = build_repo(tmp_path, source)
    test_body = (
        "import qux\n"
        + "\n"
        + "\n"
        + "def test_qux():\n"
        + "    assert qux.qux(3, 0) == 3\n"
        + "    assert qux.qux(2.5, 0) == 3\n"
    )
    test_file = write_test(tmp_path, test_body)

    start = time.monotonic()
    result = run_score(repo_root, [test_file])
    elapsed = time.monotonic() - start

    assert elapsed < 60
    assert field(result, "mutation_error") is None
    assert field(result, "mutants") >= 1
    assert field(result, "killed") == field(result, "mutants")