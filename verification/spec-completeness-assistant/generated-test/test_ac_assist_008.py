import json
import os
from pathlib import Path

import pytest

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


# Shared helper class used by every fake: readable both as attributes and
# as a mapping, since a caller may access either way.
_REC_CLASS = '''
import json as _json


class _Rec:
    def __init__(self, **kw):
        object.__setattr__(self, "_keys", list(kw))
        for k, v in kw.items():
            object.__setattr__(self, k, v)

    def __getitem__(self, k):
        if k not in self._keys:
            raise KeyError(k)
        return getattr(self, k)

    def get(self, k, default=None):
        return getattr(self, k) if k in self._keys else default

    def __contains__(self, k):
        return k in self._keys

    def __iter__(self):
        return iter(self._keys)

    def keys(self):
        return list(self._keys)

    def items(self):
        return [(k, getattr(self, k)) for k in self._keys]

    def values(self):
        return [getattr(self, k) for k in self._keys]

    def __len__(self):
        return len(self._keys)

    def to_json(self):
        return {k: getattr(self, k) for k in self._keys}


def _log(entry):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(entry) + "\\n")
'''

_LINTER_BODY = '''

class LintReport(_Rec):
    pass


def lint(paths, repo_root, strict=False, judge=None):
    _log({"fn": "lint"})
    return LintReport(
        findings=[],
        summary={"hard_failures": 0, "warnings": 0, "skipped": 0},
        hard_failures=0,
        warnings=0,
        skipped=0,
    )
'''

_IMPACT_BODY = '''

def compute_blast_radius(changed_ids, repo_root):
    _log({"fn": "compute_blast_radius", "changed_ids": list(changed_ids)})
    return _Rec(
        impacted=[{"component_id": "comp-foo", "reason": "direct", "via": None}],
        precondition_error=None,
    )
'''

_ASSEMBLER_BODY = '''

def _bundle(component_id, mode):
    return _Rec(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="Foo doubles a number.\\n\\n**R-FOO-001** \\u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\\n\\n```\\nfoo(x: int) -> int\\n```",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** \\u2014 a test term.",
        hint_code=({} if mode == "hint" else None),
    )


def assemble(component_id, repo_root, mode="cold"):
    _log({"fn": "assemble", "component_id": component_id, "mode": mode})
    return _bundle(component_id, mode)


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({"fn": "assemble_criterion", "component_id": component_id})
    return _Rec(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="",
        requirement_text="",
        interface="",
        glossary="",
        dependency_interfaces={},
    )
'''


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_corpus(repo_root: Path):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
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
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
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
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n    return 2 * x\n",
    )


def _write_fakes(repo_root: Path, log: Path):
    header = "LOG = " + repr(str(log)) + "\n"
    _write(
        repo_root / "gen" / "spec-linter" / "spec_linter.py",
        header + _REC_CLASS + _LINTER_BODY,
    )
    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        header + _REC_CLASS + _IMPACT_BODY,
    )
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        header + _REC_CLASS + _ASSEMBLER_BODY,
    )


def _snapshot(root: Path):
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(root)
            if "__pycache__" in rel.parts:
                continue
            snap[rel.as_posix()] = p.read_bytes()
    return snap


def test_ac_assist_008_report_exposes_decision_hook_and_repo_unchanged(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "invocations.log"

    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    _write_corpus(repo_root)
    _write_fakes(repo_root, log)

    before = _snapshot(repo_root)
    assert before, "fixture snapshot should not be empty"

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    # The faked dependencies were the ones actually used.
    assert log.is_file(), "faked spec-linter was never invoked"
    calls = [json.loads(line) for line in log.read_text().splitlines() if line]
    assert any(c["fn"] == "lint" for c in calls)

    # The report exposes every field a calling tool needs to record an
    # accept/override decision against this component's suggestions,
    # none silently omitted, even in degraded (no-model) mode.
    for name in (
        "lint_findings",
        "predicted_blast_radius",
        "hint_previews",
        "completeness_score",
        "completeness_rationale",
        "redundancy_flags",
        "degraded",
    ):
        assert has_field(report, name), f"report is missing field {name!r}"

    assert field(report, "degraded") is True
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    flags = field(report, "redundancy_flags")
    assert flags is None or list(flags) == []
    assert list(field(report, "lint_findings")) == []
    assert "comp-foo" in list(field(report, "predicted_blast_radius"))

    # repo_root is unchanged, ignoring Python's own __pycache__.
    after = _snapshot(repo_root)
    assert set(after) == set(before), (
        "files added/removed under repo_root: "
        f"added={sorted(set(after) - set(before))}, "
        f"removed={sorted(set(before) - set(after))}"
    )
    changed = sorted(k for k in before if before[k] != after[k])
    assert changed == [], f"files modified under repo_root: {changed}"