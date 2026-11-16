import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_HELPERS = '''
import json
from pathlib import Path


class _AttrDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _log(entry):
    log_path = Path(__file__).resolve().parents[2] / "fake_calls.log"
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\\n")
'''


FAKE_SPEC_LINTER = COMMON_HELPERS + '''

class LintReport:
    def __init__(self, findings):
        self.findings = list(findings)

    @property
    def hard_failures(self):
        return sum(1 for f in self.findings if getattr(f, "severity", None) == "fail")

    @property
    def warnings(self):
        return sum(1 for f in self.findings if getattr(f, "severity", None) == "warn")

    @property
    def skipped(self):
        return sum(1 for f in self.findings if getattr(f, "severity", None) == "skipped")

    @property
    def summary(self):
        return {
            "hard_failures": self.hard_failures,
            "warnings": self.warnings,
            "skipped": self.skipped,
        }

    def to_json(self):
        return {"findings": [], "summary": self.summary}

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
    _log({"fn": "lint"})
    return LintReport([])
'''


FAKE_IMPACT_ANALYZER = COMMON_HELPERS + '''

def compute_blast_radius(changed_ids, repo_root):
    _log({"fn": "compute_blast_radius", "changed_ids": list(changed_ids)})
    return _AttrDict(
        impacted=[
            _AttrDict(component_id="comp-alpha", reason="direct", via=None),
            _AttrDict(component_id="comp-beta", reason="transitive-interface", via="comp-alpha"),
        ],
        precondition_error=None,
    )
'''


FAKE_SPEC_BUNDLE_ASSEMBLER = COMMON_HELPERS + '''

class SpecBundle:
    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )

    def __init__(self, component_id, spec_bundle_hash, spec, interface, constraints,
                 dependency_interfaces=None, dependency_context=None,
                 dependency_usage=None, vars=None, glossary="", hint_code=None):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.spec = spec
        self.interface = interface
        self.constraints = constraints
        self.dependency_interfaces = dependency_interfaces or {}
        self.dependency_context = dependency_context or {}
        self.dependency_usage = dependency_usage or {}
        self.vars = vars or {}
        self.glossary = glossary
        self.hint_code = hint_code

    def __getitem__(self, key):
        if key in self._FIELDS:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


def assemble(component_id, repo_root, mode="cold"):
    _log({"fn": "assemble", "component_id": component_id, "mode": mode})
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="spec of " + component_id,
        interface="interface of " + component_id,
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** - a test term.",
        hint_code={} if mode == "hint" else None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError("not used in this test")
'''


FAKE_GENERATOR = COMMON_HELPERS + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log({"fn": "generate"})
    get = bundle.get if hasattr(bundle, "get") else (lambda k, d=None: getattr(bundle, k, d))
    return _AttrDict(
        component_id=get("component_id"),
        spec_bundle_hash=get("spec_bundle_hash"),
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"placeholder.py": "x = 1\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root: Path, slug: str, depends_on: str) -> None:
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        f"depends_on: {depends_on}\n"
        "---\n"
        "\n"
        f"# {slug.capitalize()}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{slug.capitalize()} doubles a number.\n",
    )
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — `{slug}(x)` MUST return `2 * x`.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        f"When {slug}(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        base / "interface" / "library.md",
        f"# Library\n\n```\n{slug}(x: int) -> int\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _build_repo(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    _write_component(repo_root, "alpha", "[]")
    _write_component(repo_root, "beta", "[comp-alpha]")

    gen = repo_root / "gen"
    _write(gen / "spec-linter" / "spec_linter.py", FAKE_SPEC_LINTER)
    _write(gen / "impact-analyzer" / "impact_analyzer.py", FAKE_IMPACT_ANALYZER)
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", FAKE_SPEC_BUNDLE_ASSEMBLER)
    _write(gen / "generator" / "generator.py", FAKE_GENERATOR)


def _read_log(repo_root: Path):
    log_path = repo_root / "fake_calls.log"
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _component_id_of(entry):
    if isinstance(entry, str):
        return entry
    return field(entry, "component_id")


def test_ac_assist_002_predicted_blast_radius_from_impact_analyzer(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    monkeypatch.chdir(tmp_path)

    report = spec_completeness_assistant.assist(["R-ALPHA-001"], repo_root)

    calls = _read_log(repo_root)
    assert any(c.get("fn") == "compute_blast_radius" for c in calls), (
        f"faked impact-analyzer was never invoked; calls: {calls}"
    )

    radius = field(report, "predicted_blast_radius")
    assert radius is not None
    ids = [_component_id_of(e) for e in list(radius)]
    assert len(ids) == 2, f"expected exactly two components, got {ids}"
    assert sorted(ids) == ["comp-alpha", "comp-beta"]