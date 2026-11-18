# hotdocs-criterion: sha256:22b0b01879bc5d82a3527ed0335b92e8e9a0bcd09a23f9b3c192e420a8dbb27e
"""AC-IMPACT-011: usage errors exit with code 2.

Covers: R-IMPACT-001

Given a lint-clean corpus containing comp-foo and no comp-nope:
- `hotdocs impact --changed comp-nope --repo-root=<repo_root>` exits 2,
  names comp-nope on stderr, and prints nothing on stdout.
- `hotdocs impact --repo-root=<repo_root>` with no --changed exits 2.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

import impact_analyzer


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


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-foo]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo performs a small, well-defined transformation for its callers.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the foo transformation.\n"
    "- Out of scope: everything else.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "None.\n"
    "\n"
    "## Behavior\n"
    "\n"
    "See `requirements/`.\n"
    "\n"
    "## Interfaces\n"
    "\n"
    "See `interface/`.\n"
    "\n"
    "## Data\n"
    "\n"
    "See `interface/data/`.\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "See `acceptance/`.\n"
    "\n"
    "## Non-functional constraints\n"
    "\n"
    "See `constraints.md`.\n"
    "\n"
    "## Open questions\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial version.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — The component MUST return its input unchanged.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given an input value\n"
    "When foo runs on it\n"
    "Then it returns the same value\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- Latency: each call completes in under 100 ms, measured by a timed test run.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** — the transformation performed by comp-foo.\n"
)


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(root / "specs" / "glossary.md", GLOSSARY_MD)
    _write(root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return x\n")
    (root / "gen").mkdir(parents=True, exist_ok=True)
    (root / "verification").mkdir(parents=True, exist_ok=True)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, root)
    assert report.hard_failures == 0, [
        (f.rule_id, f.file, f.message) for f in report.findings
    ]
    return root


def _run(argv, capsys):
    capsys.readouterr()  # discard anything printed during setup
    try:
        rc = impact_analyzer.main(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            rc = 0
        elif isinstance(code, int):
            rc = code
        else:
            rc = 1
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_unknown_changed_id_is_usage_error(repo_root, capsys):
    rc, out, err = _run(
        ["--changed", "comp-nope", "--repo-root=" + str(repo_root)], capsys
    )
    assert rc == 2
    assert "comp-nope" in err
    assert out == ""


def test_missing_changed_is_usage_error(repo_root, capsys):
    rc, out, err = _run(["--repo-root=" + str(repo_root)], capsys)
    assert rc == 2