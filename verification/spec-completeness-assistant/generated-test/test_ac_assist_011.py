# hotdocs-criterion: sha256:b7cb8394e95a57bc65ec6ea3e9e4b5f64c8f0d5bfd64251bda5774678071d0af
import importlib.util
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _linter_source(log_path):
    return (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('lint\\n')\n"
        "    return {\n"
        "        'findings': [],\n"
        "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},\n"
        "    }\n"
    )


def _impact_source(log_path, component_id, tag):
    return (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(" + repr(tag + "\n") + ")\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': " + repr(component_id) + ", 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )


def _reviewer_source(log_path):
    return (
        "class _ReviewReport:\n"
        "    def __init__(self, targets):\n"
        "        self.targets = list(targets)\n"
        "        self.criteria_checked = []\n"
        "        self.findings = []\n"
        "        self.gaps = []\n"
        "        self.writable = {}\n"
        "        self.lint_findings = []\n"
        "        self.proposals = []\n"
        "        self.degraded = True\n"
        "    def __getitem__(self, key):\n"
        "        return self.to_dict()[key]\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'targets': list(self.targets),\n"
        "            'criteria_checked': [],\n"
        "            'findings': [],\n"
        "            'gaps': [],\n"
        "            'writable': {},\n"
        "            'lint_findings': [],\n"
        "            'proposals': [],\n"
        "            'degraded': True,\n"
        "        }\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check ' + ','.join(targets) + '\\n')\n"
        "    return _ReviewReport(targets)\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )


def _endpoint_source(log_path):
    return (
        "def complete(prompt, model, backend=None, **params):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {\n"
        "        'text': '{}',\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )


def test_ac_assist_011_dependencies_resolved_per_call(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = tmp_path / "tool"
    tool_gen = tool_root / "gen"

    source = Path(spec_completeness_assistant.__file__).read_bytes()
    copy_path = tool_gen / "spec-completeness-assistant" / "spec_completeness_assistant.py"
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_bytes(source)

    _write(tool_gen / "spec-linter" / "spec_linter.py", _linter_source(log_path))
    _write(
        tool_gen / "impact-analyzer" / "impact_analyzer.py",
        _impact_source(log_path, "comp-tool", "impact tool"),
    )
    _write(tool_gen / "spec-reviewer" / "spec_reviewer.py", _reviewer_source(log_path))
    _write(tool_gen / "llm-endpoint" / "llm_endpoint.py", _endpoint_source(log_path))

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / "gen").exists()

    module_name = "spec_completeness_assistant_ac_assist_011_copy"
    saved = sys.modules.get(module_name)
    try:
        copy = load_module(copy_path, module_name)

        # First scenario: no repo_root/gen/, everything from the tool root.
        report1 = copy.assist(["R-FOO-001"], repo_root)
        assert list(field(report1, "predicted_blast_radius")) == ["comp-tool"]

        log1 = log_path.read_text(encoding="utf-8").splitlines()
        assert "impact tool" in log1
        assert "lint" in log1

        # Second scenario: repo_root's own impact-analyzer stand-in wins,
        # and nothing loaded by the earlier call is reused.
        _write(
            repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
            _impact_source(log_path, "comp-mine", "impact mine"),
        )
        log_path.write_text("", encoding="utf-8")

        report2 = copy.assist(["R-FOO-001"], repo_root)
        assert list(field(report2, "predicted_blast_radius")) == ["comp-mine"]

        log2 = log_path.read_text(encoding="utf-8").splitlines()
        assert "impact mine" in log2
        assert "impact tool" not in log2
        # The other dependencies still come from the tool root.
        assert "lint" in log2
    finally:
        if saved is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = saved