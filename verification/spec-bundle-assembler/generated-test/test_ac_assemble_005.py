import spec_bundle_assembler

import importlib.util
import sys
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _hard_failures(report):
    return report["hard_failures"] if isinstance(report, dict) else report.hard_failures


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_component(repo_root: Path, slug: str, upper: str, title: str, depends_on: str):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        f"depends_on: {depends_on}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{title} doubles a number.\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n"
        "\n"
        f"**R-{upper}-001** — `{slug}(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        f"When {slug}(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        f"{slug}(x: int) -> int\n"
        "```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


def _build_corpus(repo_root: Path):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    _write_component(repo_root, "foo", "FOO", "Foo", "[]")
    _write_component(repo_root, "bar", "BAR", "Bar", "[comp-foo]")


def _break_corpus(repo_root: Path):
    # Delete the Kind: line from bar's acceptance file: a hard lint failure.
    ac = repo_root / "specs" / "components" / "bar" / "acceptance" / "AC-BAR-001.md"
    lines = ac.read_text().splitlines(keepends=True)
    ac.write_text("".join(l for l in lines if not l.startswith("Kind:")))


@pytest.fixture
def broken_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    spec_linter = _load_spec_linter()
    assert _hard_failures(spec_linter.lint(None, repo_root)) == 0
    _break_corpus(repo_root)
    assert _hard_failures(spec_linter.lint(None, repo_root)) > 0
    return repo_root


def _looks_like_bundle(result):
    try:
        spec_text = field(result, "spec")
    except (KeyError, AttributeError, TypeError):
        return False
    return bool(spec_text)


@pytest.mark.parametrize("component_id", ["comp-foo", "comp-bar"])
def test_library_assemble_refuses_non_lint_clean_corpus(broken_repo, component_id):
    try:
        result = spec_bundle_assembler.assemble(component_id, broken_repo)
    except Exception:
        return  # precondition failure surfaced as an error: no bundle produced
    assert not _looks_like_bundle(result), (
        "assemble produced a (partial) bundle despite a hard-fail lint finding"
    )


@pytest.mark.parametrize("component_id", ["comp-foo", "comp-bar"])
def test_cli_assemble_exits_precondition_failure(broken_repo, component_id, capsys):
    code = spec_bundle_assembler.main(
        [component_id, f"--repo-root={broken_repo}", "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "spec_bundle_hash" not in out