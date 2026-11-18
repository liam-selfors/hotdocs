# hotdocs-criterion: sha256:32a966a2872ba11f5c75c00268378737c0ca4b114f0543d7bbac3c7633ff3bfa
import importlib.util
import sys
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(specs / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
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
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def _write_fakes(repo_root, log_path):
    gen = repo_root / "gen"
    log = repr(str(log_path))

    linter_src = (
        "LOG = " + log + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "class Finding:\n"
        "    def __init__(self, rule_id, severity, file, line, message, rationale=None):\n"
        "        self.rule_id = rule_id\n"
        "        self.severity = severity\n"
        "        self.file = file\n"
        "        self.line = line\n"
        "        self.message = message\n"
        "        self.rationale = rationale\n"
        "    def to_json(self):\n"
        "        d = {'rule_id': self.rule_id, 'severity': self.severity, 'file': self.file,\n"
        "             'line': self.line, 'message': self.message}\n"
        "        if self.rationale is not None:\n"
        "            d['rationale'] = self.rationale\n"
        "        return d\n"
        "\n"
        "class LintReport:\n"
        "    def __init__(self, findings):\n"
        "        self.findings = findings\n"
        "    @property\n"
        "    def hard_failures(self):\n"
        "        return sum(1 for f in self.findings if f.severity == 'fail')\n"
        "    @property\n"
        "    def warnings(self):\n"
        "        return sum(1 for f in self.findings if f.severity == 'warn')\n"
        "    @property\n"
        "    def skipped(self):\n"
        "        return sum(1 for f in self.findings if f.severity == 'skipped')\n"
        "    def to_json(self):\n"
        "        return {'findings': [f.to_json() for f in self.findings],\n"
        "                'summary': {'hard_failures': self.hard_failures,\n"
        "                            'warnings': self.warnings, 'skipped': self.skipped}}\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('lint')\n"
        "    return LintReport([])\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        "LOG = " + log + "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('compute_blast_radius\\n')\n"
        "    return {'impacted': [{'component_id': 'comp-foo', 'reason': 'direct', 'via': None}],\n"
        "            'precondition_error': None}\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    assembler_src = (
        "LOG = " + log + "\n"
        "\n"
        "_FIELDS = ('component_id', 'spec_bundle_hash', 'spec', 'interface', 'constraints',\n"
        "           'dependency_interfaces', 'dependency_context', 'dependency_usage',\n"
        "           'vars', 'glossary', 'hint_code')\n"
        "\n"
        "class SpecBundle:\n"
        "    def __init__(self, component_id, spec_bundle_hash, spec, interface, constraints,\n"
        "                 dependency_interfaces=None, dependency_context=None,\n"
        "                 dependency_usage=None, vars=None, glossary='', hint_code=None):\n"
        "        self.component_id = component_id\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.spec = spec\n"
        "        self.interface = interface\n"
        "        self.constraints = constraints\n"
        "        self.dependency_interfaces = dependency_interfaces or {}\n"
        "        self.dependency_context = dependency_context or {}\n"
        "        self.dependency_usage = dependency_usage or {}\n"
        "        self.vars = vars or {}\n"
        "        self.glossary = glossary\n"
        "        self.hint_code = hint_code\n"
        "    def __getitem__(self, key):\n"
        "        if key not in _FIELDS:\n"
        "            raise KeyError(key)\n"
        "        return getattr(self, key)\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key) if key in _FIELDS else default\n"
        "    def keys(self):\n"
        "        return list(_FIELDS)\n"
        "    def __iter__(self):\n"
        "        return iter(_FIELDS)\n"
        "    def __len__(self):\n"
        "        return len(_FIELDS)\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble ' + component_id + ' ' + mode + '\\n')\n"
        "    hint = {'foo.py': 'def foo(x):\\n    return 2 * x\\n'} if mode == 'hint' else None\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:' + '0' * 64,\n"
        "        spec='# Foo\\n\\n## Purpose\\n\\nFoo doubles a number.',\n"
        "        interface='# Library',\n"
        "        constraints='None.',\n"
        "        glossary='- **Foo** — a test term.',\n"
        "        hint_code=hint,\n"
        "    )\n"
    )
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_src)

    generator_src = (
        "LOG = " + log + "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('generate\\n')\n"
        "    return {'component_id': bundle['component_id'],\n"
        "            'spec_bundle_hash': bundle['spec_bundle_hash'],\n"
        "            'model': model, 'prompt_version': 'v10', 'cache_hit': False,\n"
        "            'files': {'foo.py': 'def foo(x):\\n    return 2 * x\\n'},\n"
        "            'model_call_error': None, 'refused': None,\n"
        "            'retry_feedback': retry_feedback}\n"
    )
    _write(gen / "generator" / "generator.py", generator_src)

    endpoint_src = (
        "LOG = " + log + "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {'text': '{}', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


FORBIDDEN = ("block", "fail", "exit", "gate", "abort", "raise", "reject", "deny", "veto", "merge")


def _public_names(report):
    if isinstance(report, dict):
        return [str(k) for k in report.keys()]
    names = [n for n in dir(report) if not n.startswith("_")]
    fields = getattr(report, "__dataclass_fields__", None)
    if fields:
        names.extend(fields.keys())
    return names


def test_ac_assist_006_report_is_advisory_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fixture(repo_root)
    _write_fakes(repo_root, log_path)

    component_md = (repo_root / "specs" / "components" / "foo" / "component.md").read_text(encoding="utf-8")
    depends_line = [ln for ln in component_md.splitlines() if ln.startswith("depends_on:")][0]
    assert "comp-spec-completeness-assistant" not in depends_line

    # Returns normally rather than raising (SystemExit included).
    try:
        report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)
    except BaseException as exc:  # noqa: BLE001
        raise AssertionError("assist() raised instead of returning a report: " + repr(exc))

    assert report is not None

    # The faked dependencies were actually used.
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert "lint" in calls
    assert "compute_blast_radius" in calls
    assert any(c.startswith("assemble comp-foo") for c in calls)

    # It is a CompletenessReport: every documented field is present.
    for name in (
        "lint_findings",
        "predicted_blast_radius",
        "hint_previews",
        "completeness_score",
        "completeness_rationale",
        "redundancy_flags",
        "degraded",
    ):
        field(report, name)

    # No field or method that blocks, fails, or exits anything.
    names = _public_names(report)
    offending = [n for n in names if any(word in n.lower() for word in FORBIDDEN)]
    assert offending == [], "report exposes gating-like members: " + repr(offending)

    # No zero-argument public method on the report exits the process.
    if not isinstance(report, dict):
        for name in [n for n in dir(report) if not n.startswith("_")]:
            member = getattr(report, name, None)
            if callable(member):
                try:
                    member()
                except SystemExit:
                    raise AssertionError("report method " + repr(name) + " exits the process")
                except BaseException:  # noqa: BLE001
                    pass