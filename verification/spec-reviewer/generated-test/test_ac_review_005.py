import importlib.util
import sys
from pathlib import Path

import spec_reviewer


REPLY = (
    '{"writable": false, "gaps": [{"kind": "guess", '
    '"missing": "the unit", "proposed_text": "x is in metres", '
    '"target_file": "specs/components/foo/interface/library.md"}]}'
)

EXPECTED_TEXT = (
    "# Proposals for AC-FOO-001\n"
    "\n"
    "- kind: guess\n"
    "  missing: the unit\n"
    "  target_file: specs/components/foo/interface/library.md\n"
    "  proposed_text: x is in metres\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
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
        "Foo doubles a number.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def _load_spec_linter():
    gen = next(
        p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


def _assert_lint_clean(repo_root):
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0


def backend(prompt, model, **params):
    return {
        "text": REPLY,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _norm(paths):
    return [str(p).replace("\\", "/") for p in paths]


def test_write_proposals_writes_one_file_per_criterion(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    report = spec_reviewer.check(
        ["AC-FOO-001"],
        repo_root,
        model="mock",
        llm_backend=backend,
        write_proposals=True,
    )

    proposals = field(report, "proposals")
    assert _norm(proposals) == [".hotdocs/proposals/AC-FOO-001.md"]

    proposal_file = repo_root / ".hotdocs" / "proposals" / "AC-FOO-001.md"
    assert proposal_file.is_file()
    assert proposal_file.read_bytes().decode("utf-8") == EXPECTED_TEXT

    written = sorted(
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / ".hotdocs" / "proposals").rglob("*")
        if p.is_file()
    )
    assert written == [".hotdocs/proposals/AC-FOO-001.md"]


def test_without_write_proposals_writes_nothing(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    report = spec_reviewer.check(
        ["AC-FOO-001"],
        repo_root,
        model="mock",
        llm_backend=backend,
    )

    proposals = field(report, "proposals")
    assert list(proposals) == []
    assert not (repo_root / ".hotdocs" / "proposals").exists()