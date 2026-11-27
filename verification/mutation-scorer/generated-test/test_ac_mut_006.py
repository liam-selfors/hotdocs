# hotdocs-criterion: sha256:45e8c9df41ace8288a150c69143e9ba5af5b7a47578b367cfcec4dc4dcbd0385
import importlib.util
import sys
from pathlib import Path

import pytest

import mutation_scorer


LINE_1_MESSAGE = (
    "javascript in a string at qux.py:1; declare it as an asset "
    "(specs/architecture/asset-kinds.md)"
)


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


def write_fixture(tmp_path, script_value):
    repo_root = tmp_path / "repo"
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
        "SCRIPT = " + repr(script_value) + "\n\n\ndef qux():\n    return 4\n"
    )

    tests_dir = tmp_path / "tests_outside"
    tests_dir.mkdir()
    test_file = tests_dir / "test_qux_value.py"
    test_file.write_text(
        "import qux\n"
        + "\n"
        + "\n"
        + "def test_qux_returns_four():\n"
        + "    assert qux.qux() == 4\n"
    )
    return repo_root, test_file


CASES = [
    ("function f(a) { return a; }" + " " * 200, LINE_1_MESSAGE),
    ("function f(a) ; return a" + " " * 200, LINE_1_MESSAGE),
    ("function f(a) { return a; }" + " " * 100, None),
    ("plain words, no code here; {x}" + " " * 200, None),
    ("function f(a) return a" + " " * 200, None),
]


@pytest.mark.parametrize(
    "script_value,expected_error",
    CASES,
    ids=[
        "braces-long",
        "semicolon-long",
        "braces-short",
        "no-js-pattern",
        "no-semicolon-or-brace",
    ],
)
def test_ac_mut_006_javascript_in_string(tmp_path, script_value, expected_error):
    repo_root, test_file = write_fixture(tmp_path, script_value)

    run_environment = load_run_environment()
    environment = run_environment.prepare("comp-qux", repo_root)
    try:
        assert field(environment, "ok") is True

        result = mutation_scorer.score(
            "comp-qux", repo_root, [str(test_file.resolve())], environment
        )

        mutation_error = field(result, "mutation_error")
        mutation_score = field(result, "mutation_score")

        if expected_error is None:
            assert mutation_error is None
            assert mutation_score is not None
        else:
            assert mutation_error == expected_error
            assert mutation_score is None
    finally:
        environment.close()