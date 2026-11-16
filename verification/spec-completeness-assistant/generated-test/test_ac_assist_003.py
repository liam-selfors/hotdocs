import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


_MAPPING_MIXIN = '''
import dataclasses
import json
import uuid
from dataclasses import dataclass, field as _dc_field

LOG_PATH = __LOG_PATH__


def _log(record):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\\n")


def _read(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _MapMixin:
    _extra_keys = ()

    def keys(self):
        return [f.name for f in dataclasses.fields(self)] + list(self._extra_keys)

    def __getitem__(self, key):
        if key in self.keys():
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        return key in self.keys()

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def values(self):
        return [self[k] for k in self.keys()]
'''


_SPEC_LINTER = _MAPPING_MIXIN + '''

@dataclass
class Finding(_MapMixin):
    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    rationale: object = None

    def to_json(self):
        d = {"rule_id": self.rule_id, "severity": self.severity, "file": self.file,
             "line": self.line, "message": self.message}
        if self.rationale is not None:
            d["rationale"] = self.rationale
        return d


@dataclass
class LintReport(_MapMixin):
    findings: list = _dc_field(default_factory=list)
    _extra_keys = ("summary", "hard_failures", "warnings", "skipped")

    @property
    def hard_failures(self):
        return sum(1 for f in self.findings if _read(f, "severity") == "fail")

    @property
    def warnings(self):
        return sum(1 for f in self.findings if _read(f, "severity") == "warn")

    @property
    def skipped(self):
        return sum(1 for f in self.findings if _read(f, "severity") == "skipped")

    @property
    def summary(self):
        return {"hard_failures": self.hard_failures, "warnings": self.warnings,
                "skipped": self.skipped}

    def to_json(self):
        return {"findings": [f.to_json() for f in self.findings], "summary": self.summary}


def lint(paths, repo_root, strict=False, judge=None):
    _log({"fn": "lint"})
    return LintReport(findings=[])
'''


_IMPACT_ANALYZER = _MAPPING_MIXIN + '''

@dataclass
class ImpactedComponent(_MapMixin):
    component_id: str
    reason: str
    via: object = None


@dataclass
class BlastRadiusReport(_MapMixin):
    impacted: list = _dc_field(default_factory=list)
    precondition_error: object = None

    def to_json(self):
        return {"impacted": [{"component_id": i.component_id, "reason": i.reason,
                              "via": i.via} for i in self.impacted],
                "precondition_error": self.precondition_error}


def compute_blast_radius(changed_ids, repo_root):
    _log({"fn": "compute_blast_radius", "changed_ids": list(changed_ids)})
    return BlastRadiusReport(
        impacted=[ImpactedComponent(component_id="comp-foo", reason="direct", via=None)],
        precondition_error=None,
    )
'''


_SPEC_BUNDLE_ASSEMBLER = _MAPPING_MIXIN + '''

@dataclass
class SpecBundle(_MapMixin):
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
class CriterionBundle(_MapMixin):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = _dc_field(default_factory=dict)


def assemble(component_id, repo_root, mode="cold"):
    nonce = uuid.uuid4().hex
    _log({"fn": "assemble", "component_id": component_id, "mode": mode, "nonce": nonce})
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + nonce,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        glossary="- **Foo** \\u2014 a test term.",
        hint_code=({"foo.py": "def foo(x):\\n    return 2 * x\\n"} if mode == "hint" else None),
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({"fn": "assemble_criterion", "component_id": component_id,
          "criterion_id": criterion_id})
    return CriterionBundle(
        component_id=component_id, criterion_id=criterion_id, covers="R-FOO-001",
        criterion_text="", requirement_text="", interface="", glossary="",
    )
'''


_GENERATOR = _MAPPING_MIXIN + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


@dataclass
class GenerationResult(_MapMixin):
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: object
    model_call_error: object
    refused: object
    retry_feedback: object


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = _read(bundle, "component_id")
    bundle_hash = _read(bundle, "spec_bundle_hash")
    _log({"fn": "generate", "component_id": component_id,
          "spec_bundle_hash": bundle_hash, "model": model})
    return GenerationResult(
        component_id=component_id,
        spec_bundle_hash=bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


_LLM_ENDPOINT = _MAPPING_MIXIN + '''

DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log({"fn": "complete", "model": model})
    text = json.dumps({
        "score": 0.9,
        "completeness_score": 0.9,
        "rationale": "Looks complete.",
        "completeness_rationale": "Looks complete.",
        "redundancy_flags": [],
        "flags": [],
    })
    return {"text": text, "model": model, "backend": "fake", "model_call_error": None}
'''


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_fixture_corpus(repo_root: Path):
    specs = repo_root / "specs"
    _write(specs / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = specs / "components" / "foo"
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
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")


def _setup(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    _write_fixture_corpus(repo_root)

    fakes = {
        ("spec-linter", "spec_linter"): _SPEC_LINTER,
        ("impact-analyzer", "impact_analyzer"): _IMPACT_ANALYZER,
        ("spec-bundle-assembler", "spec_bundle_assembler"): _SPEC_BUNDLE_ASSEMBLER,
        ("generator", "generator"): _GENERATOR,
        ("llm-endpoint", "llm_endpoint"): _LLM_ENDPOINT,
    }
    for (slug, module_name), source in fakes.items():
        _write(
            repo_root / "gen" / slug / f"{module_name}.py",
            source.replace("__LOG_PATH__", repr(str(log_path))),
        )
    return repo_root, log_path


def _read_log(log_path: Path):
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_with_model_hint_previews_generated_from_hint_bundle(tmp_path):
    repo_root, log_path = _setup(tmp_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    hint_previews = field(report, "hint_previews")
    assert list(hint_previews.keys()) == ["comp-foo"]

    log = _read_log(log_path)
    assembles = [r for r in log if r["fn"] == "assemble"]
    assert assembles, f"assemble never called; log: {log}"
    assert all(r["mode"] == "hint" for r in assembles), f"non-hint assemble seen: {assembles}"
    assert not any(r["mode"] == "cold" for r in assembles)
    foo_assembles = [r for r in assembles if r["component_id"] == "comp-foo"]
    assert foo_assembles, f"assemble not called for comp-foo: {assembles}"

    generates = [r for r in log if r["fn"] == "generate"]
    assert len(generates) == 1, f"expected exactly one generate call; log: {log}"
    gen_call = generates[0]
    assert gen_call["component_id"] == "comp-foo"
    assert gen_call["model"] == "fake-model"
    assembled_hashes = {"sha256:" + r["nonce"] for r in foo_assembles}
    assert gen_call["spec_bundle_hash"] in assembled_hashes


def test_without_model_hint_preview_is_bundle_and_generate_never_called(tmp_path):
    repo_root, log_path = _setup(tmp_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    hint_previews = field(report, "hint_previews")
    assert list(hint_previews.keys()) == ["comp-foo"]

    log = _read_log(log_path)
    assembles = [r for r in log if r["fn"] == "assemble"]
    assert assembles, f"assemble never called; log: {log}"
    assert all(r["mode"] == "hint" for r in assembles), f"non-hint assemble seen: {assembles}"
    assert any(r["component_id"] == "comp-foo" for r in assembles)

    generates = [r for r in log if r["fn"] == "generate"]
    assert generates == [], f"generate must not be called without a model; log: {log}"