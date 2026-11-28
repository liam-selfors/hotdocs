# hotdocs-criterion: sha256:b46346a40e38f3504a72e83e9d8fb0181f6ad8978146419679cc473cb6bb7a48
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

REQ_001 = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

AC_001 = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

REPLY_TEXT = json.dumps(
    {
        "writable": False,
        "gaps": [
            {
                "kind": "guess",
                "missing": "the unit",
                "proposed_text": "x is in metres",
                "target_file": "specs/components/foo/interface/library.md",
            }
        ],
    }
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", GLOSSARY)
    comp = specs / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQ_001)
    write(comp / "acceptance" / "AC-FOO-001.md", AC_001)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)


def assert_lint_clean(repo_root):
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
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def backend(prompt, model, **params):
    return {
        "text": REPLY_TEXT,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def normalize(paths):
    return [str(p).replace("\\", "/") for p in paths]


def test_write_proposals_writes_one_file_per_criterion(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    assert_lint_clean(repo_root)

    report = spec_reviewer.check(
        ["AC-FOO-001"],
        repo_root,
        model="mock",
        llm_backend=backend,
        write_proposals=True,
    )

    proposals = field(report, "proposals")
    assert normalize(proposals) == [".hotdocs/proposals/AC-FOO-001.md"]

    proposal_file = repo_root / ".hotdocs" / "proposals" / "AC-FOO-001.md"
    assert proposal_file.is_file()
    assert proposal_file.read_text(encoding="utf-8") == EXPECTED_TEXT


def test_without_write_proposals_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    assert_lint_clean(repo_root)

    report = spec_reviewer.check(
        ["AC-FOO-001"],
        repo_root,
        model="mock",
        llm_backend=backend,
    )

    proposals = field(report, "proposals")
    assert list(proposals) == []
    assert not (repo_root / ".hotdocs" / "proposals").exists()