import importlib.util
import sys
from pathlib import Path

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _tool_gen_dir() -> Path:
    return next(
        p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen"
    )


def _load_spec_linter():
    base = _tool_gen_dir() / "spec-linter"
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

R_FOO_001 = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
R_FOO_002 = "# R-FOO-002\n\n**R-FOO-002** — `bar(x)` MUST return `x + 1`.\n"

AC_FOO_001 = (
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

AC_FOO_002 = (
    "# AC-FOO-002\n"
    "\n"
    "Covers: R-FOO-002\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When bar(x) is called\n"
    "Then it returns 3\n"
    "```\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "foo(x: int) -> int\n"
    "bar(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", R_FOO_001)
    _write(comp / "requirements" / "R-FOO-002.md", R_FOO_002)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_FOO_001)
    _write(comp / "acceptance" / "AC-FOO-002.md", AC_FOO_002)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)


GAP_REPLY = (
    'Here: {"writable": false, "gaps": [{"kind": "unstated_behavior", '
    '"missing": "negative x", "proposed_text": "MUST raise ValueError", '
    '"target_file": "R-FOO-001.md"}, {"kind": "other", "missing": "m", '
    '"proposed_text": "p", "target_file": "t"}]} done'
)


def _is_judge_prompt(prompt: str) -> bool:
    return (
        "conflicts" in prompt
        and "AC-FOO-001" not in prompt
        and "AC-FOO-002" not in prompt
    )


def test_ac_review_004_one_call_per_criterion_parsed_and_unparseable(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    # llm-endpoint writes its call log under the current directory.
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        text = GAP_REPLY if "AC-FOO-001" in prompt else "not json"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = spec_reviewer.check(
        ["comp-foo"], repo_root, model="mock", llm_backend=backend
    )

    # Exactly two non-judge prompts, one per criterion, kept separate.
    criterion_prompts = [p for p in prompts if not _is_judge_prompt(p)]
    assert len(criterion_prompts) == 2, criterion_prompts

    foo1_prompts = [p for p in criterion_prompts if "AC-FOO-001" in p]
    assert len(foo1_prompts) == 1
    assert "AC-FOO-002" not in foo1_prompts[0]

    # writable
    writable = field(result, "writable")
    assert dict(writable) == {"AC-FOO-001": False, "AC-FOO-002": None}
    assert writable["AC-FOO-001"] is False
    assert writable["AC-FOO-002"] is None

    # gaps: only the allowed-kind gap survives, tagged with its criterion.
    gaps = list(field(result, "gaps"))
    assert len(gaps) == 1, gaps
    gap = gaps[0]
    assert field(gap, "kind") == "unstated_behavior"
    assert field(gap, "criterion_id") == "AC-FOO-001"
    assert field(gap, "missing") == "negative x"
    assert field(gap, "proposed_text") == "MUST raise ValueError"
    assert field(gap, "target_file") == "R-FOO-001.md"

    # findings: one model_unparseable finding, for AC-FOO-002.
    findings = list(field(result, "findings"))
    unparseable = [f for f in findings if field(f, "kind") == "model_unparseable"]
    assert len(unparseable) == 1, findings
    finding = unparseable[0]
    assert field(finding, "criterion_id") == "AC-FOO-002"
    assert field(finding, "token") == ""
    assert field(finding, "message") == "reply was not the JSON object asked for"

    # degraded
    assert field(result, "degraded") is False