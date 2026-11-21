# hotdocs-criterion: sha256:228fa25d7da2a547545810fdc618d0d616e94719d2617c0702c141515ccd1e50
import importlib.util
import json
import sys
from pathlib import Path

import spec_reviewer


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called with `--fast`\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", GLOSSARY)
    comp = specs / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)


def load_spec_linter():
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0
    return repo_root


def test_json_format_reports_invisible_flag(tmp_path, capsys):
    repo_root = make_repo(tmp_path)
    capsys.readouterr()
    code = spec_reviewer.main(["comp-foo", "--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    findings = field(doc, "findings")
    assert len(findings) == 1
    assert field(findings[0], "token") == "--fast"


def test_strict_text_returns_one_with_summary(tmp_path, capsys):
    repo_root = make_repo(tmp_path)
    capsys.readouterr()
    code = spec_reviewer.main(["comp-foo", "--strict", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, "expected output on stdout"
    assert lines[-1].strip() == "1 criteria checked, 1 findings, 0 gaps"


def test_usage_errors_return_two(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path)
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
        assert code == 2, argv
        err_lines = captured.err.splitlines()
        assert err_lines, argv
        assert err_lines[0].startswith("usage error: "), (argv, captured.err)
        assert "Traceback" not in captured.err, argv
        assert "Traceback" not in captured.out, argv