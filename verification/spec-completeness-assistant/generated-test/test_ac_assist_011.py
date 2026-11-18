# hotdocs-criterion: sha256:0ad1ffeb20c5e72467fb93b8c3898771b9cfa1773babed229c223fadfd724935
import importlib.util
import shutil
import sys
from pathlib import Path

import spec_completeness_assistant


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ATTRDICT_SRC = (
    "class AttrDict(dict):\n"
    "    def __getattr__(self, name):\n"
    "        try:\n"
    "            return self[name]\n"
    "        except KeyError:\n"
    "            raise AttributeError(name)\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
)


def lint_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        + ATTRDICT_SRC
        + "class Finding:\n"
        "    def __init__(self, rule_id, severity, file, line, message, rationale=None):\n"
        "        self.rule_id = rule_id\n"
        "        self.severity = severity\n"
        "        self.file = file\n"
        "        self.line = line\n"
        "        self.message = message\n"
        "        self.rationale = rationale\n"
        "\n"
        "    def to_json(self):\n"
        "        d = {'rule_id': self.rule_id, 'severity': self.severity, 'file': self.file,\n"
        "             'line': self.line, 'message': self.message}\n"
        "        if self.rationale is not None:\n"
        "            d['rationale'] = self.rationale\n"
        "        return d\n"
        "\n"
        "\n"
        "class LintReport:\n"
        "    def __init__(self, findings):\n"
        "        self.findings = findings\n"
        "\n"
        "    @property\n"
        "    def hard_failures(self):\n"
        "        return sum(1 for f in self.findings if f.severity == 'fail')\n"
        "\n"
        "    @property\n"
        "    def warnings(self):\n"
        "        return sum(1 for f in self.findings if f.severity == 'warn')\n"
        "\n"
        "    @property\n"
        "    def skipped(self):\n"
        "        return sum(1 for f in self.findings if f.severity == 'skipped')\n"
        "\n"
        "    def to_json(self):\n"
        "        return {'findings': [f.to_json() for f in self.findings],\n"
        "                'summary': {'hard_failures': self.hard_failures,\n"
        "                            'warnings': self.warnings,\n"
        "                            'skipped': self.skipped}}\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        if key == 'findings':\n"
        "            return self.findings\n"
        "        return self.to_json()[key]\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        try:\n"
        "            return self[key]\n"
        "        except KeyError:\n"
        "            return default\n"
        "\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('lint')\n"
        "    return LintReport([])\n"
        "\n"
        "\n"
        "def load_corpus(repo_root):\n"
        "    raise NotImplementedError('stand-in')\n"
    )


def impact_source(log_path, component_id, tag):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        + ATTRDICT_SRC
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('impact ' + " + repr(tag) + ")\n"
        "    return AttrDict({\n"
        "        'impacted': [AttrDict({'component_id': " + repr(component_id) + ",\n"
        "                               'reason': 'direct', 'via': None})],\n"
        "        'precondition_error': None,\n"
        "    })\n"
    )


def assembler_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        + ATTRDICT_SRC
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble ' + component_id)\n"
        "    return AttrDict({\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'spec': 'spec text',\n"
        "        'interface': 'interface text',\n"
        "        'constraints': 'None.',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': ({} if mode == 'hint' else None),\n"
        "    })\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion ' + component_id)\n"
        "    return AttrDict({\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': '',\n"
        "        'criterion_text': '',\n"
        "        'requirement_text': '',\n"
        "        'interface': '',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "    })\n"
    )


def generator_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        + ATTRDICT_SRC
        + "GATE_VERSION = 'generator@2.0.0'\n"
        "PROMPT_VERSION = 'v10'\n"
        "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generate')\n"
        "    cid = bundle['component_id'] if isinstance(bundle, dict) else bundle.component_id\n"
        "    h = bundle['spec_bundle_hash'] if isinstance(bundle, dict) else bundle.spec_bundle_hash\n"
        "    return AttrDict({\n"
        "        'component_id': cid,\n"
        "        'spec_bundle_hash': h,\n"
        "        'model': model,\n"
        "        'prompt_version': PROMPT_VERSION,\n"
        "        'cache_hit': False,\n"
        "        'files': {'x.py': 'pass\\n'},\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "    })\n"
    )


def endpoint_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        + ATTRDICT_SRC
        + "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('complete')\n"
        "    return {'text': '{}', 'model': model, 'backend': 'stand-in',\n"
        "            'model_call_error': None}\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_tool_root(t, log_path):
    gen = t / "gen"
    own = gen / "spec-completeness-assistant" / "spec_completeness_assistant.py"
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_bytes(Path(spec_completeness_assistant.__file__).read_bytes())
    write(gen / "spec-linter" / "spec_linter.py", lint_source(log_path))
    write(gen / "impact-analyzer" / "impact_analyzer.py",
          impact_source(log_path, "comp-tool", "tool"))
    write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
          assembler_source(log_path))
    write(gen / "generator" / "generator.py", generator_source(log_path))
    write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_source(log_path))
    return own


def run_copy(own_path, module_name, repo_root):
    previous = sys.modules.get(module_name)
    try:
        copy = load_module(own_path, module_name)
        return copy.assist(["R-FOO-001"], repo_root)
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous


def read_log(log_path):
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8").splitlines()


def test_dependency_loaded_from_tool_root_when_repo_has_no_gen(tmp_path):
    t = tmp_path / "toolroot"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    own = build_tool_root(t, log_path)
    assert not (repo_root / "gen").exists()

    report = run_copy(own, "spec_completeness_assistant_copy_toolroot", repo_root)

    assert list(field(report, "predicted_blast_radius")) == ["comp-tool"]
    assert "impact tool" in read_log(log_path)


def test_dependency_loaded_from_repo_root_gen_when_present(tmp_path):
    t = tmp_path / "toolroot"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    own = build_tool_root(t, log_path)
    write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
          impact_source(log_path, "comp-mine", "mine"))

    report = run_copy(own, "spec_completeness_assistant_copy_reporoot", repo_root)

    assert list(field(report, "predicted_blast_radius")) == ["comp-mine"]
    lines = read_log(log_path)
    assert "impact mine" in lines
    assert "impact tool" not in lines