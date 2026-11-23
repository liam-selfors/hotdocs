# hotdocs-criterion: sha256:3a89c105b9920da3209d3cf2b65bb060731321bfcd79471826882b985e69291d
import importlib.util
import json
import sys
from pathlib import Path

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FENCE = "```"

GLOSSARY = "# Glossary\n" + "\n" + "- **Foo** — a test term.\n"

COMPONENT = (
    "---\n"
    + "id: comp-foo\n"
    + "title: Foo\n"
    + "status: draft\n"
    + "owners: [team-a]\n"
    + "sealed: true\n"
    + "source_path: legacy/foo/\n"
    + "depends_on: []\n"
    + "---\n"
    + "\n"
    + "# Foo\n"
    + "\n"
    + "## Purpose\n"
    + "\n"
    + "Foo doubles a number.\n"
)

REQUIREMENT = (
    "# R-FOO-001\n"
    + "\n"
    + "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
)

CRITERION = (
    "# AC-FOO-001\n"
    + "\n"
    + "Covers: R-FOO-001\n"
    + "Kind: generated-test\n"
    + "\n"
    + FENCE + "gherkin\n"
    + "Given x = 2\n"
    + "When foo(x) is called with `--fast`\n"
    + "Then it returns 4\n"
    + FENCE + "\n"
)

LIBRARY = (
    "# Library\n"
    + "\n"
    + FENCE + "\n"
    + "foo(x: int) -> int\n"
    + FENCE + "\n"
)

CONSTRAINTS = "# Constraints\n" + "\n" + "None.\n"


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    foo = specs / "components" / "foo"
    _write(specs / "glossary.md", GLOSSARY)
    _write(foo / "component.md", COMPONENT)
    _write(foo / "requirements" / "R-FOO-001.md", REQUIREMENT)
    _write(foo / "acceptance" / "AC-FOO-001.md", CRITERION)
    _write(foo / "interface" / "library.md", LIBRARY)
    _write(foo / "constraints.md", CONSTRAINTS)


def _assert_lint_clean(repo_root):
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec_linter = load_module(path, "spec_linter")
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def _corpus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)
    return repo_root


def test_json_format_reports_one_invisible_fast_token(tmp_path, capsys):
    repo_root = _corpus(tmp_path)
    capsys.readouterr()

    code = spec_reviewer.main(["comp-foo", "--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 0
    doc = json.loads(out)
    findings = field(doc, "findings")
    assert len(findings) == 1
    assert field(findings[0], "token") == "--fast"


def test_strict_text_returns_1_with_summary_line(tmp_path, capsys):
    repo_root = _corpus(tmp_path)
    capsys.readouterr()

    code = spec_reviewer.main(["comp-foo", "--strict", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, "no stdout output"
    assert lines[-1] == "1 criteria checked, 1 findings, 0 gaps"


def test_usage_errors_return_2(tmp_path, capsys, monkeypatch):
    repo_root = _corpus(tmp_path)
    monkeypatch.chdir(repo_root)
    capsys.readouterr()

    cases = [
        ["AC-FOO-404", "--repo-root=" + str(repo_root)],
        ["comp-foo", "--format=bogus"],
        ["comp-foo", "--model"],
        [],
    ]
    for argv in cases:
        code = spec_reviewer.main(list(argv))
        captured = capsys.readouterr()
        assert code == 2, "argv " + repr(argv) + " returned " + repr(code)
        err_lines = captured.err.splitlines()
        assert err_lines, "argv " + repr(argv) + " printed nothing to stderr"
        assert err_lines[0].startswith("usage error: "), (
            "argv " + repr(argv) + " stderr first line: " + repr(err_lines[0])
        )
        assert "Traceback" not in captured.err, "argv " + repr(argv) + " printed a traceback"
        assert "Traceback" not in captured.out, "argv " + repr(argv) + " printed a traceback"