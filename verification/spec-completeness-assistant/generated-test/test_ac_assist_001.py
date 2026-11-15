import importlib.util
import sys
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _opt_field(value, name):
    if isinstance(value, dict):
        return value.get(name, None)
    return getattr(value, name, None)


# --------------------------------------------------------------------------
# Tool-root spec-linter (real), used only to confirm the fixture lints clean
# --------------------------------------------------------------------------

def _real_spec_linter_path():
    gen = next(
        p for p in Path(spec_completeness_assistant.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    if (base / "spec_linter.py").is_file():
        return base / "spec_linter.py"
    return base / "spec_linter" / "__init__.py"


def _load_real_spec_linter():
    path = _real_spec_linter_path()
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Synthetic, lint-clean corpus
# --------------------------------------------------------------------------

GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

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

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE_MD = (
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

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "foo(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def _write_corpus(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (specs / "glossary.md").write_text(GLOSSARY)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "interface" / "library.md").write_text(LIBRARY_MD)
    (comp / "constraints.md").write_text(CONSTRAINTS_MD)


# --------------------------------------------------------------------------
# Fake dependency modules
# --------------------------------------------------------------------------

FAKE_SPEC_LINTER = '''
import importlib.util
import sys
from dataclasses import dataclass, field as _dc_field

LOG_PATH = __LOG__
REAL_LINTER_PATH = __REAL__
FINDING_DATA = __FINDING__


def _log(name):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(name + "\\n")


_FINDING_FIELDS = ("rule_id", "severity", "file", "line", "message", "rationale")


@dataclass
class Finding:
    rule_id: object
    severity: object
    file: object
    line: object
    message: object
    rationale: object = None

    def to_json(self):
        d = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }
        if self.rationale is not None:
            d["rationale"] = self.rationale
        return d

    def __getitem__(self, key):
        if key in _FINDING_FIELDS:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in _FINDING_FIELDS:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self.to_json().keys())


@dataclass
class LintReport:
    findings: list = _dc_field(default_factory=list)

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

    def __getitem__(self, key):
        if key in ("findings", "summary", "hard_failures", "warnings", "skipped"):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def lint(paths, repo_root, strict=False, judge=None):
    _log("spec-linter")
    return LintReport(findings=[Finding(**FINDING_DATA)])


_REAL = None


def _real():
    global _REAL
    if _REAL is None:
        name = "_fake_delegate_real_spec_linter"
        spec = importlib.util.spec_from_file_location(name, REAL_LINTER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _REAL = module
    return _REAL


def load_corpus(repo_root):
    return _real().load_corpus(repo_root)
'''

FAKE_IMPACT_ANALYZER = '''
LOG_PATH = __LOG__


def _log(name):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(name + "\\n")


class BlastRadiusReport(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def compute_blast_radius(changed_ids, repo_root):
    _log("impact-analyzer")
    return BlastRadiusReport(impacted=[], precondition_error=None)
'''

FAKE_SPEC_BUNDLE_ASSEMBLER = '''
LOG_PATH = __LOG__


def _log(name):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(name + "\\n")


class SpecBundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def assemble(component_id, repo_root, mode="cold"):
    _log("spec-bundle-assembler")
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="",
        interface="",
        constraints="",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code={} if mode == "hint" else None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("spec-bundle-assembler")
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
        "dependency_interfaces": {},
    }
'''

FAKE_GENERATOR = '''
LOG_PATH = __LOG__

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def _log(name):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(name + "\\n")


class GenerationResult(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generator")
    cid = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    sbh = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash")
    return GenerationResult(
        component_id=cid,
        spec_bundle_hash=sbh,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''

FAKE_LLM_ENDPOINT = '''
import json

LOG_PATH = __LOG__
DEFAULT_TIMEOUT_SECONDS = 600


def _log(name):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(name + "\\n")


def complete(prompt, model, *, backend=None, **params):
    _log("llm-endpoint")
    text = json.dumps({
        "completeness_score": 0.5,
        "completeness_rationale": "fake rationale",
        "score": 0.5,
        "rationale": "fake rationale",
        "redundancy_flags": [],
    })
    return {
        "text": text,
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }
'''


def _write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source)


def _setup(tmp_path, finding):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    log.write_text("")

    _write_corpus(repo_root)
    # Confirm the synthetic corpus is lint-clean under the real linter.
    real_linter = _load_real_spec_linter()
    report = real_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    log_lit = repr(str(log))
    _write_fake(
        repo_root,
        "spec-linter",
        FAKE_SPEC_LINTER.replace("__LOG__", log_lit)
        .replace("__REAL__", repr(str(_real_spec_linter_path())))
        .replace("__FINDING__", repr(finding)),
    )
    _write_fake(repo_root, "impact-analyzer", FAKE_IMPACT_ANALYZER.replace("__LOG__", log_lit))
    _write_fake(
        repo_root, "spec-bundle-assembler",
        FAKE_SPEC_BUNDLE_ASSEMBLER.replace("__LOG__", log_lit),
    )
    _write_fake(repo_root, "generator", FAKE_GENERATOR.replace("__LOG__", log_lit))
    _write_fake(repo_root, "llm-endpoint", FAKE_LLM_ENDPOINT.replace("__LOG__", log_lit))
    return repo_root, log


def _log_entries(log):
    return [line.strip() for line in log.read_text().splitlines() if line.strip()]


FAIL_FINDING = {
    "rule_id": "R-LINT-003",
    "severity": "fail",
    "file": "specs/components/foo/component.md",
    "line": 12,
    "message": "depends_on references 'comp-bar', which does not exist",
}

WARN_FINDING = {
    "rule_id": "R-LINT-015",
    "severity": "warn",
    "file": "specs/components/foo/component.md",
    "line": 3,
    "message": "a warning-only finding",
}


def test_fail_finding_halts_before_any_other_dependency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo_root, log = _setup(tmp_path, FAIL_FINDING)

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    findings = list(field(report, "lint_findings"))
    assert len(findings) == 1
    got = findings[0]
    for key, expected in FAIL_FINDING.items():
        assert field(got, key) == expected, key
    # No rationale added when lint gave none.
    if isinstance(got, dict):
        assert "rationale" not in got
    else:
        assert _opt_field(got, "rationale") is None

    assert list(field(report, "predicted_blast_radius")) == []
    assert dict(field(report, "hint_previews")) == {}
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []

    entries = _log_entries(log)
    assert "impact-analyzer" not in entries
    assert "generator" not in entries
    assert "llm-endpoint" not in entries


def test_warn_only_finding_proceeds_to_impact_analyzer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo_root, log = _setup(tmp_path, WARN_FINDING)

    spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    entries = _log_entries(log)
    assert "impact-analyzer" in entries