# hotdocs-criterion: sha256:78b4fe8a3cc59ce89e71fa98717258e77c3cbd3cacdc31d543fea6fa89639c5f
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


def _own_module_file():
    path = Path(spec_completeness_assistant.__file__).resolve()
    if path.name == "__init__.py":
        # Spec says one flat module file; tolerate a package layout by
        # copying its __init__.py as the flat module.
        return path
    return path


def _linter_source(log_path):
    return (
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('lint\\n')\n"
        "    return {\n"
        "        'findings': [],\n"
        "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},\n"
        "    }\n"
    )


def _impact_source(log_path, component_id, tag):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "COMPONENT_ID = " + repr(component_id) + "\n"
        "TAG = " + repr(tag) + "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('compute_blast_radius ' + TAG + '\\n')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {\n"
        "                'component_id': COMPONENT_ID,\n"
        "                'reason': 'direct',\n"
        "                'via': None,\n"
        "            }\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )


def _reviewer_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
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
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'targets': list(self.targets),\n"
        "            'criteria_checked': list(self.criteria_checked),\n"
        "            'findings': list(self.findings),\n"
        "            'gaps': list(self.gaps),\n"
        "            'writable': dict(self.writable),\n"
        "            'lint_findings': list(self.lint_findings),\n"
        "            'proposals': list(self.proposals),\n"
        "            'degraded': self.degraded,\n"
        "        }\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('check\\n')\n"
        "    return _ReviewReport(targets)\n"
        "\n"
        "def _judge(term, local_text, glossary_text):\n"
        "    return None\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('glossary_judge\\n')\n"
        "    return _judge\n"
    )


def _endpoint_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {\n"
        "        'text': None,\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': {'category': 'network', 'message': 'stand-in'},\n"
        "    }\n"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _setup(tmp_path, copy_name):
    tool_root = tmp_path / "toolroot"
    log_path = tmp_path / "calls.log"
    log_path.write_text("")

    own = _own_module_file()
    copy_path = (
        tool_root
        / "gen"
        / "spec-completeness-assistant"
        / "spec_completeness_assistant.py"
    )
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_bytes(own.read_bytes())

    _write(
        tool_root / "gen" / "spec-linter" / "spec_linter.py",
        _linter_source(log_path),
    )
    _write(
        tool_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        _impact_source(log_path, "comp-tool", "tool"),
    )
    _write(
        tool_root / "gen" / "spec-reviewer" / "spec_reviewer.py",
        _reviewer_source(log_path),
    )
    _write(
        tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        _endpoint_source(log_path),
    )

    repo_root = tmp_path / "project"
    repo_root.mkdir()
    assert not (repo_root / "gen").exists()

    module = load_module(copy_path, copy_name)
    return module, repo_root, log_path


def _log_lines(log_path):
    return [line for line in log_path.read_text().splitlines() if line]


def test_tool_root_dependencies_used_when_repo_has_no_gen(tmp_path):
    copy, repo_root, log_path = _setup(
        tmp_path, "spec_completeness_assistant_ac_assist_011_a"
    )

    report = copy.assist(["R-FOO-001"], repo_root)

    assert list(field(report, "predicted_blast_radius")) == ["comp-tool"]
    lines = _log_lines(log_path)
    assert "compute_blast_radius tool" in lines
    assert not (repo_root / "gen").exists()


def test_repo_root_dependency_overrides_tool_root_per_dependency(tmp_path):
    copy, repo_root, log_path = _setup(
        tmp_path, "spec_completeness_assistant_ac_assist_011_b"
    )

    first = copy.assist(["R-FOO-001"], repo_root)
    assert list(field(first, "predicted_blast_radius")) == ["comp-tool"]

    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        _impact_source(log_path, "comp-mine", "mine"),
    )

    second = copy.assist(["R-FOO-001"], repo_root)
    assert list(field(second, "predicted_blast_radius")) == ["comp-mine"]

    lines = _log_lines(log_path)
    assert "compute_blast_radius mine" in lines
    # The other dependencies still came from the tool root on the second call.
    assert lines.count("lint") >= 2
    assert not field(second, "halted")