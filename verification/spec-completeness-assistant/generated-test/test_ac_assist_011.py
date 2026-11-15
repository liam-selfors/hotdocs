import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest

import spec_completeness_assistant


DEP_MODULE_NAMES = (
    "spec_linter",
    "impact_analyzer",
    "spec_bundle_assembler",
    "generator",
    "llm_endpoint",
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ATTRDICT_SRC = '''
class _AttrDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
'''


def _linter_src(log_path):
    return (
        "import json\n"
        "LOG = %r\n" % str(log_path)
        + '''

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

    def to_json(self):
        return {
            "findings": [],
            "summary": {
                "hard_failures": self.hard_failures,
                "warnings": self.warnings,
                "skipped": self.skipped,
            },
        }

    def __getitem__(self, key):
        if key in ("findings", "hard_failures", "warnings", "skipped"):
            return getattr(self, key)
        if key == "summary":
            return self.to_json()["summary"]
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def lint(paths, repo_root, strict=False, judge=None):
    with open(LOG, "a") as fh:
        fh.write(json.dumps({"fn": "lint", "repo_root": str(repo_root)}) + "\\n")
    return LintReport([])
'''
    )


def _impact_src(log_path, component_id):
    return (
        "import json\n"
        + ATTRDICT_SRC
        + "LOG = %r\n" % str(log_path)
        + "COMPONENT_ID = %r\n" % component_id
        + '''

def compute_blast_radius(changed_ids, repo_root):
    with open(LOG, "a") as fh:
        fh.write(json.dumps({
            "fn": "compute_blast_radius",
            "changed_ids": list(changed_ids),
            "repo_root": str(repo_root),
        }) + "\\n")
    return _AttrDict({
        "impacted": [
            _AttrDict({"component_id": COMPONENT_ID, "reason": "direct", "via": None}),
        ],
        "precondition_error": None,
    })
'''
    )


def _assembler_src(log_path):
    return (
        "import json\n"
        "LOG = %r\n" % str(log_path)
        + '''

_FIELDS = (
    "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
    "dependency_interfaces", "dependency_context", "dependency_usage",
    "vars", "glossary", "hint_code",
)


class SpecBundle:
    def __init__(self, component_id, spec_bundle_hash, spec, interface,
                 constraints, dependency_interfaces=None, dependency_context=None,
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
        if key in _FIELDS:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key) if key in _FIELDS else default

    def keys(self):
        return list(_FIELDS)

    def __iter__(self):
        return iter(_FIELDS)

    def __len__(self):
        return len(_FIELDS)

    def __contains__(self, key):
        return key in _FIELDS


def assemble(component_id, repo_root, mode="cold"):
    with open(LOG, "a") as fh:
        fh.write(json.dumps({
            "fn": "assemble", "component_id": component_id, "mode": mode,
        }) + "\\n")
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="spec text",
        interface="interface text",
        constraints="None.",
        glossary="",
        hint_code={} if mode == "hint" else None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    raise AssertionError("assemble_criterion is not expected to be called")
'''
    )


def _generator_src():
    return ATTRDICT_SRC + '''

def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    cid = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    h = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash")
    return _AttrDict({
        "component_id": cid,
        "spec_bundle_hash": h,
        "model": model,
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"x.py": "# stub\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    })
'''


def _llm_endpoint_src():
    return '''

def complete(prompt, model, *, backend=None, **params):
    if backend is not None:
        return backend(prompt, model, **params)
    return {
        "text": "{}",
        "model": model,
        "backend": "stub",
        "model_call_error": None,
    }
'''


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_tool_root(t, logs):
    gen = t / "gen"
    src = Path(spec_completeness_assistant.__file__).resolve()
    target_dir = gen / "spec-completeness-assistant"
    target_dir.mkdir(parents=True, exist_ok=True)
    if src.name == "__init__.py":
        pkg_dir = target_dir / "spec_completeness_assistant"
        shutil.copytree(src.parent, pkg_dir, ignore=shutil.ignore_patterns("__pycache__"))
        copy_path = pkg_dir / "__init__.py"
        assert copy_path.read_bytes() == src.read_bytes()
        is_pkg = True
    else:
        copy_path = target_dir / "spec_completeness_assistant.py"
        copy_path.write_bytes(src.read_bytes())
        is_pkg = False

    _write(gen / "spec-linter" / "spec_linter.py", _linter_src(logs / "tool_lint.log"))
    _write(
        gen / "impact-analyzer" / "impact_analyzer.py",
        _impact_src(logs / "tool_impact.log", "comp-tool"),
    )
    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _assembler_src(logs / "tool_assemble.log"),
    )
    _write(gen / "generator" / "generator.py", _generator_src())
    _write(gen / "llm-endpoint" / "llm_endpoint.py", _llm_endpoint_src())
    return copy_path, is_pkg


def _load_copy(copy_path, is_pkg):
    name = "spec_completeness_assistant_copy_" + uuid.uuid4().hex
    if is_pkg:
        spec = importlib.util.spec_from_file_location(
            name, copy_path, submodule_search_locations=[str(copy_path.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location(name, copy_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clean_dep_modules():
    saved = {n: sys.modules.pop(n) for n in DEP_MODULE_NAMES if n in sys.modules}
    try:
        yield
    finally:
        for n in DEP_MODULE_NAMES:
            sys.modules.pop(n, None)
        sys.modules.update(saved)


def _read_log(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_ac_assist_011_falls_back_to_tool_root(tmp_path, clean_dep_modules):
    logs = tmp_path / "logs"
    logs.mkdir()
    t = tmp_path / "tool"
    copy_path, is_pkg = _build_tool_root(t, logs)

    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    assert not (repo_root / "gen").exists()

    module = _load_copy(copy_path, is_pkg)
    report = module.assist(["R-FOO-001"], repo_root)

    assert list(field(report, "predicted_blast_radius")) == ["comp-tool"]
    assert len(_read_log(logs / "tool_impact.log")) >= 1


def test_ac_assist_011_prefers_repo_root_gen(tmp_path, clean_dep_modules):
    logs = tmp_path / "logs"
    logs.mkdir()
    t = tmp_path / "tool"
    copy_path, is_pkg = _build_tool_root(t, logs)

    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        _impact_src(logs / "mine_impact.log", "comp-mine"),
    )

    module = _load_copy(copy_path, is_pkg)
    report = module.assist(["R-FOO-001"], repo_root)

    assert list(field(report, "predicted_blast_radius")) == ["comp-mine"]
    assert len(_read_log(logs / "mine_impact.log")) >= 1
    assert _read_log(logs / "tool_impact.log") == []