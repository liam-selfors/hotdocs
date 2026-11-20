# hotdocs-criterion: sha256:b32f3e3e720ec3878175a2c0d2f23af92fb21e543dc2a0c3ad8992082d3d6f06
import importlib.util
import json
import os
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
    path.write_text(text)


def write_component(repo, slug):
    upper = slug.upper()
    title = slug.title()
    base = repo / "specs" / "components" / slug
    sections = [
        "Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
        "Acceptance criteria", "Open questions", "Change log",
    ]
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
    for s in sections:
        lines.append("")
        lines.append("## " + s)
        lines.append("")
        lines.append("Text for " + s.lower() + ".")
    write(base / "component.md", "\n".join(lines) + "\n")
    rid = "R-" + upper + "-001"
    aid = "AC-" + upper + "-001"
    write(base / "requirements" / (rid + ".md"),
          "# " + rid + "\n\nThe component MUST return its input unchanged.\n")
    write(base / "acceptance" / (aid + ".md"),
          "# " + aid + "\n\n"
          "Covers: " + rid + "\n"
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


def _linter_file(base):
    flat = base / "spec_linter.py"
    if flat.is_file():
        return flat
    pkg = base / "spec_linter" / "__init__.py"
    if pkg.is_file():
        return pkg
    return None


def find_spec_linter_path():
    starts = []
    try:
        starts.append(Path(impact_analyzer.__file__).resolve())
    except Exception:
        pass
    starts.append(Path(os.getcwd()).resolve())
    for start in starts:
        for p in [start] + list(start.parents):
            if p.name == "gen":
                found = _linter_file(p / "spec-linter")
                if found:
                    return found
            found = _linter_file(p / "gen" / "spec-linter")
            if found:
                return found
    spec = importlib.util.find_spec("spec_linter")
    if spec is not None and spec.origin and spec.origin not in ("built-in", "frozen"):
        return Path(spec.origin)
    return None


def load_spec_linter():
    path = find_spec_linter_path()
    if path is None:
        return None
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


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
    if spec_linter is not None:
        assert spec_linter.lint(None, tmp_path).hard_failures == 0
    return tmp_path


def usage_cases(r):
    return [
        ["--changed", "comp-foo", "--format", "text", "comp-qux", "--repo-root", r],
        ["--changed", "comp-foo", "-x", "--repo-root", r],
        ["--repo-root", r, "--changed"],
        ["--changed", "comp-foo", "--repo-root"],
        ["--changed", "comp-foo", "--format"],
        ["--changed", "comp-foo", "--format=yaml", "--repo-root", r],
    ]


@pytest.mark.parametrize("index", range(6))
def test_usage_errors(repo, capsys, monkeypatch, index):
    monkeypatch.chdir(repo)
    argv = usage_cases(str(repo))[index]
    capsys.readouterr()
    code = impact_analyzer.main(argv)
    out, err = capsys.readouterr()
    assert code == 2, (argv, code, out, err)
    assert out == "", (argv, out)
    lines = err.splitlines()
    first = lines[0] if lines else ""
    assert first.startswith("usage error: "), (argv, err)


def test_changed_takes_following_ids_json(repo, capsys, monkeypatch):
    monkeypatch.chdir(repo)
    capsys.readouterr()
    code = impact_analyzer.main([
        "--changed", "comp-foo", "comp-qux", "--format", "json",
        "--repo-root", str(repo),
    ])
    out, err = capsys.readouterr()
    assert code == 0, (out, err)
    doc = json.loads(out)
    ids = [field(e, "component_id") for e in field(doc, "impacted")]
    assert ids == ["comp-foo", "comp-qux"]