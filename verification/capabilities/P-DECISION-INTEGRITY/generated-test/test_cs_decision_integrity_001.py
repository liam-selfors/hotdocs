import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

import decision_drift_detector


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git_env():
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test Author",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return env


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo),
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(did, title, status, last_ratified_commit, supersedes=None):
    lines = [
        "---",
        f"id: {did}",
        f"title: {title}",
        f"status: {status}",
        "owners: [pipeline-team]",
        f"last_ratified_commit: {last_ratified_commit}",
    ]
    if supersedes is not None:
        lines.append(f"supersedes: {supersedes}")
    lines.append("---")
    body = (
        "\n"
        f"# {did}: {title}\n"
        "\n"
        "## Context\n"
        "\n"
        "A synthetic decision used by a test fixture.\n"
        "\n"
        "## Decision\n"
        "\n"
        f"{title}.\n"
    )
    return "\n".join(lines) + "\n" + body


def _load_spec_linter():
    module_file = Path(decision_drift_detector.__file__).resolve()
    tool_root = None
    for parent in module_file.parents:
        if parent.name == "gen":
            tool_root = parent.parent
            break
    assert tool_root is not None, (
        f"could not locate a 'gen' directory above {module_file}"
    )
    flat = tool_root / "gen" / "spec-linter" / "spec_linter.py"
    pkg = tool_root / "gen" / "spec-linter" / "spec_linter" / "__init__.py"
    path = flat if flat.is_file() else pkg
    assert path.is_file(), f"spec_linter not found under {tool_root / 'gen'}"
    module_name = "spec_linter"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


CITING_FILE = "specs/components/foo/requirements/R-FOO-001.md"


@pytest.fixture
def repo_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")

    # Commit 1: the earlier decision D1 is introduced.
    _write(
        repo / "specs" / "decisions" / "D1.md",
        _decision("D1", "Foo does things the original way", "ratified", "0000000"),
    )
    _write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a synthetic fixture term.\n",
    )
    c1 = _commit(repo, "Add D1")

    # Commit 2: record D1's ratification, and add a live spec file citing D1.
    _write(
        repo / "specs" / "decisions" / "D1.md",
        _decision("D1", "Foo does things the original way", "ratified", c1),
    )
    comp_dir = repo / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A synthetic sealed component used by a test fixture.\n",
    )
    _write(
        repo / CITING_FILE,
        "# R-FOO-001\n"
        "\n"
        "Foo MUST do things the original way (`D1`).\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo\n"
        "When it runs\n"
        "Then it does things\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nrun() -> None\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo / "legacy" / "foo" / "foo.py", "def run():\n    return None\n")
    _commit(repo, "Record last_ratified_commit for D1; add comp-foo citing D1")

    # Commit 3: D2 supersedes D1 (scalar supersedes line); D1 deprecated.
    _write(
        repo / "specs" / "decisions" / "D1.md",
        _decision("D1", "Foo does things the original way", "deprecated", c1),
    )
    _write(
        repo / "specs" / "decisions" / "D2.md",
        _decision(
            "D2",
            "Foo does things a new way",
            "ratified",
            "0000000",
            supersedes="D1",
        ),
    )
    c3 = _commit(repo, "Add D2, superseding D1")

    # Commit 4: record D2's ratification commit.
    _write(
        repo / "specs" / "decisions" / "D2.md",
        _decision(
            "D2",
            "Foo does things a new way",
            "ratified",
            c3,
            supersedes="D1",
        ),
    )
    _commit(repo, "Record last_ratified_commit for D2")

    # Sanity: the frontmatter holds exactly the scalar line.
    d2_text = (repo / "specs" / "decisions" / "D2.md").read_text(encoding="utf-8")
    assert "\nsupersedes: D1\n" in d2_text

    return repo


def _normalize(repo_root, file_value):
    p = Path(str(file_value))
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(repo_root.resolve())
        except ValueError:
            pass
    return p.as_posix()


def test_cs_decision_integrity_001_stale_citation_appears_in_drift_report(repo_root):
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0, f"fixture has hard lint failures: {report}"

    drift = decision_drift_detector.find_decision_drift(repo_root)
    entries = list(field(drift, "entries"))

    pairs = [
        (_normalize(repo_root, field(e, "file")), str(field(e, "cited_decision")))
        for e in entries
    ]
    assert (CITING_FILE, "D1") in pairs, (
        f"expected ({CITING_FILE!r}, 'D1') in drift report, got {pairs!r}"
    )

    matching = [
        e
        for e in entries
        if _normalize(repo_root, field(e, "file")) == CITING_FILE
        and str(field(e, "cited_decision")) == "D1"
    ]
    assert any(str(field(e, "superseded_by")) == "D2" for e in matching), (
        f"expected the D1 citation to be reported as superseded by D2: {matching!r}"
    )