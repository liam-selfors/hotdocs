import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_SPEC_LINTER = '''import json
import dataclasses

LOG_PATH = __LOG__


def _log(function, **details):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"module": "spec_linter", "function": function, "details": details}) + "\\n")


@dataclasses.dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    rationale: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

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


@dataclasses.dataclass
class LintReport:
    findings: list = dataclasses.field(default_factory=list)

    @property
    def hard_failures(self):
        return sum(1 for f in self.findings if f.severity == "fail")

    @property
    def warnings(self):
        return sum(1 for f in self.findings if f.severity == "warn")

    @property
    def skipped(self):
        return sum(1 for f in self.findings if f.severity == "skipped")

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_json(self):
        return {
            "findings": [f.to_json() for f in self.findings],
            "summary": {
                "hard_failures": self.hard_failures,
                "warnings": self.warnings,
                "skipped": self.skipped,
            },
        }


def lint(paths, repo_root, strict=False, judge=None):
    _log("lint", paths=None if paths is None else [str(p) for p in paths], strict=bool(strict))
    return LintReport(findings=[
        Finding(
            rule_id="R-LINT-009",
            severity="warn",
            file="specs/components/foo/component.md",
            line=3,
            message="fake warn finding",
        )
    ])
'''


FAKE_IMPACT_ANALYZER = '''import json

LOG_PATH = __LOG__


def _log(function, **details):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"module": "impact_analyzer", "function": function, "details": details}) + "\\n")


class _Record(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def compute_blast_radius(changed_ids, repo_root):
    _log("compute_blast_radius", changed_ids=list(changed_ids))
    return _Record({
        "impacted": [_Record({"component_id": "comp-foo", "reason": "direct", "via": None})],
        "precondition_error": None,
    })
'''


FAKE_ASSEMBLER = '''import json
import hashlib
import dataclasses

LOG_PATH = __LOG__


def _log(function, **details):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"module": "spec_bundle_assembler", "function": function, "details": details}) + "\\n")


@dataclasses.dataclass
class SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self.keys() else default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __contains__(self, key):
        return key in self.keys()

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def values(self):
        return [getattr(self, k) for k in self.keys()]


@dataclasses.dataclass
class CriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    spec = "Foo doubles a number.\\n\\n# R-FOO-001\\n\\n**R-FOO-001** \\u2014 `foo(x)` MUST return `2 * x`."
    digest = hashlib.sha256((component_id + spec).encode("utf-8")).hexdigest()
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + digest,
        spec=spec,
        interface="# Library\\n\\n```\\nfoo(x: int) -> int\\n```",
        constraints="None.",
        glossary="# Glossary\\n\\n- **Foo** \\u2014 a test term.",
        hint_code=({} if mode == "hint" else None),
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2 When foo(x) is called Then it returns 4",
        requirement_text="`foo(x)` MUST return `2 * x`.",
        interface="# Library",
        glossary="# Glossary",
    )
'''


FAKE_GENERATOR = '''import json
import dataclasses

LOG_PATH = __LOG__

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def _log(function, **details):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"module": "generator", "function": function, "details": details}) + "\\n")


@dataclasses.dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: object
    model_call_error: object
    refused: object
    retry_feedback: object

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", model=str(model))
    cid = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id", "comp-foo")
    h = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash", "sha256:0")
    return GenerationResult(
        component_id=cid,
        spec_bundle_hash=h,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


FAKE_LLM_ENDPOINT = '''import json

LOG_PATH = __LOG__

DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def _log(function, **details):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"module": "llm_endpoint", "function": function, "details": details}) + "\\n")


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=str(model))
    return {
        "text": '{"score": 0.5, "rationale": "fake", "flags": []}',
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }


def parse_model(model):
    _log("parse_model", model=str(model))
    return (None, model)
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
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
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
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
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def _read_log(log_path: Path):
    if not log_path.is_file():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def test_ac_assist_007_no_model_degraded_mode(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_literal = repr(str(log_path))

    _write_corpus(repo_root)

    gen = repo_root / "gen"
    _write(gen / "spec-linter" / "spec_linter.py", FAKE_SPEC_LINTER.replace("__LOG__", log_literal))
    _write(gen / "impact-analyzer" / "impact_analyzer.py", FAKE_IMPACT_ANALYZER.replace("__LOG__", log_literal))
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", FAKE_ASSEMBLER.replace("__LOG__", log_literal))
    _write(gen / "generator" / "generator.py", FAKE_GENERATOR.replace("__LOG__", log_literal))
    _write(gen / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT.replace("__LOG__", log_literal))

    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    # lint_findings holds the warn finding
    findings = list(field(report, "lint_findings"))
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "severity") == "warn"
    assert field(finding, "rule_id") == "R-LINT-009"
    assert field(finding, "file") == "specs/components/foo/component.md"
    assert field(finding, "line") == 3
    assert field(finding, "message") == "fake warn finding"

    # predicted_blast_radius is ["comp-foo"]
    assert list(field(report, "predicted_blast_radius")) == ["comp-foo"]

    # hint_previews has a comp-foo entry
    hint_previews = field(report, "hint_previews")
    assert hint_previews is not None
    assert "comp-foo" in hint_previews

    # degraded is true; R-ASSIST-004/005 reported as skipped
    assert field(report, "degraded") is True
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    redundancy_flags = field(report, "redundancy_flags")
    assert redundancy_flags is not None
    assert list(redundancy_flags) == []

    entries = _read_log(log_path)
    modules_functions = [(e["module"], e["function"]) for e in entries]

    # R-ASSIST-001..003 still ran through the faked dependencies
    assert ("spec_linter", "lint") in modules_functions
    assert ("impact_analyzer", "compute_blast_radius") in modules_functions
    assemble_calls = [e for e in entries if e["module"] == "spec_bundle_assembler" and e["function"] == "assemble"]
    assert any(
        e["details"].get("component_id") == "comp-foo" and e["details"].get("mode") == "hint"
        for e in assemble_calls
    )

    # The log shows no llm-endpoint call (nor generator, which dispatches through it)
    assert not [e for e in entries if e["module"] == "llm_endpoint"], entries
    assert not [e for e in entries if e["module"] == "generator"], entries