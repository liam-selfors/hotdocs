# hotdocs-criterion: sha256:202bd36eb44d8358f8a4c526884a4d145dc2911816c75cfc1ca915baa8c1d643
import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import impact_analyzer


GIT = [
    "git",
    "-c", "user.name=hotdocs-test",
    "-c", "user.email=test@example.com",
    "-c", "commit.gpgsign=false",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    subprocess.run(GIT + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo, slug):
    upper = slug.upper()
    title = slug.title()
    base = repo / "specs" / "components" / slug
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
        "---",
        "",
        "# " + title,
    ]
    for section in ["Purpose", "Scope", "Definitions", "Behavior",
                    "Interfaces", "Acceptance criteria", "Open questions",
                    "Change log"]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(lines) + "\n")

    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    write(base / "requirements" / (req_id + ".md"),
          "# " + req_id + "\n\nThe component MUST return its input unchanged.\n")
    write(base / "acceptance" / (ac_id + ".md"),
          "# " + ac_id + "\n\n"
          "Covers: " + req_id + "\n"
          "Kind: generated-test\n\n"
          "```gherkin\n"
          "Given 1\n"
          "When it runs\n"
          "Then it returns 1\n"
          "```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")


def _find_spec_linter_path():
    here = Path(impact_analyzer.__file__).resolve()
    for p in here.parents:
        candidates = [p] if p.name == "gen" else [p / "gen"]
        for gen in candidates:
            base = gen / "spec-linter"
            flat = base / "spec_linter.py"
            pkg = base / "spec_linter" / "__init__.py"
            if flat.is_file():
                return flat
            if pkg.is_file():
                return pkg
    return None


def load_spec_linter():
    path = _find_spec_linter_path()
    if path is not None:
        spec = importlib.util.spec_from_file_location("spec_linter", path)
        spec_linter = importlib.util.module_from_spec(spec)
        sys.modules["spec_linter"] = spec_linter
        spec.loader.exec_module(spec_linter)
        return spec_linter
    try:
        return importlib.import_module("spec_linter")
    except Exception:
        return None


@pytest.fixture
def repo(tmp_path):
    write(tmp_path / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(tmp_path, "foo")
    write_component(tmp_path, "qux")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "A")
    git(tmp_path, "switch", "-q", "-c", "feature")

    spec_linter = load_spec_linter()
    if spec_linter is not None and hasattr(spec_linter, "lint"):
        assert spec_linter.lint(None, tmp_path).hard_failures == 0
    return tmp_path


def test_ac_impact_015_usage_errors_and_multiple_changed_ids(repo, capsys):
    r = str(repo)
    usage_cases = [
        ["--changed", "comp-foo", "--format", "text", "comp-qux", "--repo-root", r],
        ["--changed", "comp-foo", "-x", "--repo-root", r],
        ["--repo-root", r, "--changed"],
        ["--changed", "comp-foo", "--repo-root"],
        ["--changed", "comp-foo", "--format"],
        ["--changed", "comp-foo", "--format=yaml", "--repo-root", r],
    ]
    capsys.readouterr()
    for argv in usage_cases:
        code = impact_analyzer.main(list(argv))
        out, err = capsys.readouterr()
        assert code == 2, (argv, code, out, err)
        assert out == "", (argv, out)
        err_lines = err.splitlines()
        first_line = err_lines[0] if err_lines else ""
        assert first_line.startswith("usage error: "), (argv, err)

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "comp-qux", "--format", "json", "--repo-root", r]
    )
    out, err = capsys.readouterr()
    assert code == 0, (code, out, err)
    report = json.loads(out)
    impacted = field(report, "impacted")
    ids = [field(entry, "component_id") for entry in impacted]
    assert ids == ["comp-foo", "comp-qux"]