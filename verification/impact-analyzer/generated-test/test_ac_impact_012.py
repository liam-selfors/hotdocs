# hotdocs-criterion: sha256:185b716bcc620f7bebad8ec38f7a151ea17bdf22b8ddbf3c303d6be50242195b
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import impact_analyzer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_spec_linter():
    gen = next(
        p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    return load_module(path, "spec_linter")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, slug, depends_on):
    fm = "---\n"
    fm += "id: " + comp_id + "\n"
    fm += "title: " + slug.capitalize() + " component\n"
    fm += "status: draft\n"
    fm += "owners: [team-a]\n"
    if depends_on:
        fm += "depends_on: [" + ", ".join(depends_on) + "]\n"
    fm += "sealed: true\n"
    fm += "source_path: legacy/" + slug + "/\n"
    fm += "---\n"
    body = "\n# " + slug.capitalize() + " component\n\n"
    body += "## Purpose\n\nThis component does " + slug + " things for tests.\n\n"
    body += "## Rationale\n\nRecorded in `D1`.\n\n"
    body += "## Scope\n\n- In scope: " + slug + " behavior.\n- Out of scope: everything else.\n\n"
    body += "## Definitions\n\nNone.\n\n"
    body += "## Behavior\n\nSee `requirements/`.\n\n"
    body += "## Interfaces\n\nSee `interface/`.\n\n"
    body += "## Data\n\nSee `interface/data/`.\n\n"
    body += "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
    body += "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
    body += "## Open questions\n\n"
    body += "## Change log\n\n- Initial version.\n"
    return fm + body


def _build_component(specs, comp_id, slug, upper, depends_on):
    root = specs / "components" / slug
    _write(root / "component.md", _component_md(comp_id, slug, depends_on))
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        root / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\nThe component MUST do " + slug + " work (`D1`).\n",
    )
    _write(
        root / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\n"
        + "Covers: " + req_id + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given a " + slug + " input\n"
        + "When the component runs\n"
        + "Then it does " + slug + " work\n"
        + "```\n",
    )
    _write(
        root / "interface" / "library.md",
        "# Library\n\n```\n" + slug + "_run() -> None\n```\n",
    )
    _write(
        root / "constraints.md",
        "# Constraints\n\nThe component MUST finish within one second, "
        "measured by a timer around a single call.\n",
    )


def _git(repo, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=test",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@pytest.fixture
def repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    specs = repo_root / "specs"
    _build_component(specs, "comp-foo", "foo", "FOO", [])
    _build_component(specs, "comp-bar", "bar", "BAR", ["comp-foo"])
    _write(
        specs / "decisions" / "D1.md",
        "---\nid: D1\ntitle: Test decision\nstatus: draft\nowners: [team-a]\n---\n\n"
        "# D1 — Test decision\n\n## Context\n\nTest fixture context.\n\n"
        "## Decision\n\nFixture components MUST exist for testing.\n",
    )
    _write(specs / "glossary.md", "# Glossary\n\n- **Fixture** — a test corpus.\n")

    try:
        _git(repo_root, "init", "-b", "main")
    except subprocess.CalledProcessError:
        _git(repo_root, "init")
        _git(repo_root, "checkout", "-b", "main")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "initial corpus")
    return repo_root


def _run_cli(argv, cwd, monkeypatch, capsys):
    main = getattr(impact_analyzer, "main", None)
    if callable(main):
        monkeypatch.chdir(str(cwd))
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        out = capsys.readouterr().out
        return code, out
    mod_dir = str(Path(impact_analyzer.__file__).resolve().parent)
    if Path(impact_analyzer.__file__).name == "__init__.py":
        mod_dir = str(Path(impact_analyzer.__file__).resolve().parent.parent)
    env = dict(os.environ)
    env["PYTHONPATH"] = mod_dir + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "impact_analyzer", *argv],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode, proc.stdout


def test_ac_impact_012_repo_root_defaults_to_git_root_from_subdirectory(
    repo, monkeypatch, capsys
):
    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    specs_dir = repo / "specs"
    code, out = _run_cli(
        ["--changed", "comp-foo", "--format=json"], specs_dir, monkeypatch, capsys
    )

    assert code == 0, out
    report = json.loads(out)
    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    foo_entries = [e for e in impacted if field(e, "component_id") == "comp-foo"]
    assert len(foo_entries) == 1, impacted
    assert field(foo_entries[0], "reason") == "direct"