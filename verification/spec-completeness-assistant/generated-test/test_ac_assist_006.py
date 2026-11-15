import spec_completeness_assistant

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Synthetic spec fixture (lint-clean)
# ---------------------------------------------------------------------------

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

REQ_MD = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

AC_MD = (
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_spec_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)


# ---------------------------------------------------------------------------
# Fake dependency modules
# ---------------------------------------------------------------------------

_PRELUDE = '''
import dataclasses
import json
from dataclasses import dataclass, field as _dc_field


def _log(fn, **kw):
    rec = {"fn": fn}
    rec.update(kw)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\\n")


class _MappingMixin:
    _EXTRA = ()

    def _keys(self):
        return [f.name for f in dataclasses.fields(self)] + list(type(self)._EXTRA)

    def __getitem__(self, key):
        if key in self._keys():
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return list(self._keys())

    def values(self):
        return [getattr(self, k) for k in self._keys()]

    def items(self):
        return [(k, getattr(self, k)) for k in self._keys()]

    def __iter__(self):
        return iter(self._keys())

    def __len__(self):
        return len(self._keys())

    def __contains__(self, key):
        return key in self._keys()


class _AttrDict(dict):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
'''

_FAKE_SPEC_LINTER = '''

@dataclass
class Finding(_MappingMixin):
    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    rationale: object = None

    def to_json(self):
        out = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }
        if self.rationale is not None:
            out["rationale"] = self.rationale
        return out


@dataclass
class LintReport(_MappingMixin):
    findings: list = _dc_field(default_factory=list)

    _EXTRA = ("summary", "hard_failures", "warnings", "skipped")

    @property
    def hard_failures(self):
        return sum(1 for f in self.findings if f.severity == "fail")

    @property
    def warnings(self):
        return sum(1 for f in self.findings if f.severity == "warn")

    @property
    def skipped(self):
        return sum(1 for f in self.findings if f.severity == "skipped")

    @property
    def summary(self):
        return {
            "hard_failures": self.hard_failures,
            "warnings": self.warnings,
            "skipped": self.skipped,
        }

    def to_json(self):
        return {
            "findings": [f.to_json() for f in self.findings],
            "summary": self.summary,
        }


def lint(paths, repo_root, strict=False, judge=None):
    _log(
        "lint",
        paths=None if paths is None else [str(p) for p in paths],
        repo_root=str(repo_root),
        strict=strict,
    )
    return LintReport(findings=[])
'''

_FAKE_IMPACT_ANALYZER = '''

@dataclass
class BlastRadiusReport(_MappingMixin):
    impacted: list = _dc_field(default_factory=list)
    precondition_error: object = None

    def to_json(self):
        return {
            "impacted": [dict(e) for e in self.impacted],
            "precondition_error": self.precondition_error,
        }


def compute_blast_radius(changed_ids, repo_root):
    _log("compute_blast_radius", changed_ids=list(changed_ids), repo_root=str(repo_root))
    return BlastRadiusReport(
        impacted=[_AttrDict(component_id="comp-foo", reason="direct", via=None)],
        precondition_error=None,
    )
'''

_FAKE_ASSEMBLER = '''

@dataclass
class SpecBundle(_MappingMixin):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = _dc_field(default_factory=dict)
    dependency_context: dict = _dc_field(default_factory=dict)
    dependency_usage: dict = _dc_field(default_factory=dict)
    vars: dict = _dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None


@dataclass
class CriterionBundle(_MappingMixin):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = _dc_field(default_factory=dict)


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, repo_root=str(repo_root), mode=mode)
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="# Foo\\n\\n## Purpose\\n\\nFoo doubles a number.\\n\\n# R-FOO-001\\n\\n**R-FOO-001** \\u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\\n\\n```\\nfoo(x: int) -> int\\n```",
        constraints="# Constraints\\n\\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\\n\\n- **Foo** \\u2014 a test term.",
        hint_code={"foo.py": "def foo(x):\\n    return 2 * x\\n"} if mode == "hint" else None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id, repo_root=str(repo_root))
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2\\nWhen foo(x) is called\\nThen it returns 4",
        requirement_text="**R-FOO-001** \\u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\\n\\n```\\nfoo(x: int) -> int\\n```",
        glossary="# Glossary\\n\\n- **Foo** \\u2014 a test term.",
        dependency_interfaces={},
    )
'''


def _write_fake(repo_root: Path, slug: str, body: str, log_path: Path) -> None:
    module_name = slug.replace("-", "_")
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + _PRELUDE + body
    _write(repo_root / "gen" / slug / (module_name + ".py"), source)


# ---------------------------------------------------------------------------
# Real linter check of the fixture
# ---------------------------------------------------------------------------

def _tool_gen_dir():
    for p in Path(spec_completeness_assistant.__file__).resolve().parents:
        if p.name == "gen":
            return p
    return None


def _lint_fixture_clean(repo_root: Path) -> None:
    gen = _tool_gen_dir()
    if gen is None:
        return
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    if not path.is_file():
        return
    saved = sys.modules.get("spec_linter")
    try:
        spec = importlib.util.spec_from_file_location("spec_linter", path)
        spec_linter = importlib.util.module_from_spec(spec)
        sys.modules["spec_linter"] = spec_linter
        spec.loader.exec_module(spec_linter)
        report = spec_linter.lint(None, repo_root)
        hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
        assert hard == 0
    finally:
        if saved is None:
            sys.modules.pop("spec_linter", None)
        else:
            sys.modules["spec_linter"] = saved


# ---------------------------------------------------------------------------
# Name inspection: nothing that blocks, fails, or exits
# ---------------------------------------------------------------------------

_FORBIDDEN_TOKENS = {
    "block", "blocks", "blocked", "blocking", "blocker",
    "fail", "fails", "failed", "failure", "failures", "failing",
    "exit", "exits", "exited", "exitcode", "returncode",
    "gate", "gates", "gated", "gating",
    "abort", "aborts", "aborted",
    "reject", "rejects", "rejected",
    "veto", "verdict",
    "pass", "passes", "passed",
    "merge", "mergeable",
    "raise", "ok",
}

_FORBIDDEN_SUBSTRINGS = ("block", "fail", "exit")


def _is_forbidden(name: str) -> bool:
    lowered = name.lower()
    tokens = [t for t in lowered.replace("-", "_").split("_") if t]
    if any(t in _FORBIDDEN_TOKENS for t in tokens):
        return True
    return any(s in lowered for s in _FORBIDDEN_SUBSTRINGS)


def _exposed_names(report):
    names = set()
    if isinstance(report, dict):
        names.update(str(k) for k in report.keys())
    names.update(n for n in dir(report) if not n.startswith("_"))
    for meth in ("to_json", "to_dict", "as_dict"):
        fn = getattr(report, meth, None)
        if callable(fn):
            try:
                out = fn()
            except TypeError:
                continue
            if isinstance(out, str):
                try:
                    out = json.loads(out)
                except ValueError:
                    out = None
            if isinstance(out, dict):
                names.update(str(k) for k in out.keys())
    return names


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------

def test_ac_assist_006_report_is_advisory_only(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    _build_spec_fixture(repo_root)

    # The fixture component does not depend on the assistant.
    component_text = (repo_root / "specs" / "components" / "foo" / "component.md").read_text(encoding="utf-8")
    depends_line = next(l for l in component_text.splitlines() if l.startswith("depends_on:"))
    assert "comp-spec-completeness-assistant" not in depends_line

    _lint_fixture_clean(repo_root)

    log_path = tmp_path / "fake_calls.log"
    _write_fake(repo_root, "spec-linter", _FAKE_SPEC_LINTER, log_path)
    _write_fake(repo_root, "impact-analyzer", _FAKE_IMPACT_ANALYZER, log_path)
    _write_fake(repo_root, "spec-bundle-assembler", _FAKE_ASSEMBLER, log_path)

    try:
        report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)
    except BaseException as exc:  # includes SystemExit
        pytest.fail(f"assist() raised instead of returning a report: {exc!r}")

    assert report is not None

    # The fakes were the ones used.
    calls = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    fns = [c["fn"] for c in calls]
    assert "lint" in fns
    assert "compute_blast_radius" in fns

    # It is a CompletenessReport.
    assert list(field(report, "lint_findings")) == []
    assert "comp-foo" in list(field(report, "predicted_blast_radius"))

    # It exposes no field or method that blocks, fails, or exits anything.
    offending = sorted(n for n in _exposed_names(report) if _is_forbidden(n))
    assert offending == [], f"report exposes gating-like names: {offending}"