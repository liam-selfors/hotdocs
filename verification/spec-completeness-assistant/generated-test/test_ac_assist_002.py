# hotdocs-criterion: sha256:10ca4d5a3ee229e0893e339825835a711ab3ea67461b3bed791c4ca775228a77
import importlib.util
import sys
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _real_linter_path():
    gen = next(
        p
        for p in Path(spec_completeness_assistant.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    if (base / "spec_linter.py").is_file():
        return base / "spec_linter.py"
    return base / "spec_linter" / "__init__.py"


def _build_corpus(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    for slug, upper, deps in (("alpha", "ALPHA", "[]"), ("beta", "BETA", "[comp-alpha]")):
        comp = repo_root / "specs" / "components" / slug
        title = slug.capitalize()
        _write(
            comp / "component.md",
            "---\n"
            "id: comp-" + slug + "\n"
            "title: " + title + "\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "sealed: true\n"
            "source_path: legacy/" + slug + "/\n"
            "depends_on: " + deps + "\n"
            "---\n"
            "\n"
            "# " + title + "\n"
            "\n"
            "## Purpose\n"
            "\n"
            + title + " doubles a number.\n",
        )
        rid = "R-" + upper + "-001"
        acid = "AC-" + upper + "-001"
        _write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** \u2014 `" + slug + "(x)` MUST return `2 * x`.\n",
        )
        _write(
            comp / "acceptance" / (acid + ".md"),
            "# " + acid + "\n"
            "\n"
            "Covers: " + rid + "\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When " + slug + "(x) is called\n"
            "Then it returns 4\n"
            "```\n",
        )
        _write(
            comp / "interface" / "library.md",
            "# Library\n\n```\n" + slug + "(x: int) -> int\n```\n",
        )
        _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


_LOG_HELPER = (
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
)


def _fake_spec_linter(log_path, real_linter_path):
    return (
        "import importlib.util\n"
        "import sys\n"
        "from dataclasses import dataclass, field\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REAL_LINTER_PATH = " + repr(str(real_linter_path)) + "\n"
        "\n"
        + _LOG_HELPER +
        "@dataclass\n"
        "class Finding:\n"
        "    rule_id: str\n"
        "    severity: str\n"
        "    file: str\n"
        "    line: int\n"
        "    message: str\n"
        "    rationale: str = None\n"
        "\n"
        "    def to_json(self):\n"
        "        out = {'rule_id': self.rule_id, 'severity': self.severity, 'file': self.file,\n"
        "               'line': self.line, 'message': self.message}\n"
        "        if self.rationale is not None:\n"
        "            out['rationale'] = self.rationale\n"
        "        return out\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class LintReport:\n"
        "    findings: list = field(default_factory=list)\n"
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
        "    @property\n"
        "    def summary(self):\n"
        "        return {'hard_failures': self.hard_failures, 'warnings': self.warnings,\n"
        "                'skipped': self.skipped}\n"
        "\n"
        "    def to_json(self):\n"
        "        return {'findings': [f.to_json() for f in self.findings], 'summary': self.summary}\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('lint')\n"
        "    return LintReport(findings=[])\n"
        "\n"
        "\n"
        "def load_corpus(repo_root):\n"
        "    name = '_real_spec_linter_for_fake'\n"
        "    mod = sys.modules.get(name)\n"
        "    if mod is None:\n"
        "        spec = importlib.util.spec_from_file_location(name, REAL_LINTER_PATH)\n"
        "        mod = importlib.util.module_from_spec(spec)\n"
        "        sys.modules[name] = mod\n"
        "        spec.loader.exec_module(mod)\n"
        "    return mod.load_corpus(Path(repo_root))\n"
    )


def _fake_impact_analyzer(log_path):
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        + _LOG_HELPER +
        "class BlastRadiusReport(dict):\n"
        "    def __getattr__(self, name):\n"
        "        try:\n"
        "            return self[name]\n"
        "        except KeyError:\n"
        "            raise AttributeError(name)\n"
        "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('compute_blast_radius ' + ','.join(changed_ids))\n"
        "    return BlastRadiusReport({\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-alpha', 'reason': 'direct', 'via': None},\n"
        "            {'component_id': 'comp-beta', 'reason': 'transitive-interface',\n"
        "             'via': 'comp-alpha'},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    })\n"
    )


def _fake_spec_bundle_assembler(log_path):
    return (
        "from dataclasses import dataclass, field\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        + _LOG_HELPER +
        "@dataclass\n"
        "class SpecBundle:\n"
        "    component_id: str\n"
        "    spec_bundle_hash: str\n"
        "    spec: str\n"
        "    interface: str\n"
        "    constraints: str\n"
        "    dependency_interfaces: dict = field(default_factory=dict)\n"
        "    dependency_context: dict = field(default_factory=dict)\n"
        "    dependency_usage: dict = field(default_factory=dict)\n"
        "    vars: dict = field(default_factory=dict)\n"
        "    glossary: str = ''\n"
        "    hint_code: dict = None\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "    def keys(self):\n"
        "        return list(self.__dataclass_fields__.keys())\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CriterionBundle:\n"
        "    component_id: str\n"
        "    criterion_id: str\n"
        "    covers: str\n"
        "    criterion_text: str\n"
        "    requirement_text: str\n"
        "    interface: str\n"
        "    glossary: str\n"
        "    dependency_interfaces: dict = field(default_factory=dict)\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble ' + component_id + ' ' + mode)\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:' + '0' * 64,\n"
        "        spec='spec text',\n"
        "        interface='interface text',\n"
        "        constraints='None.',\n"
        "        dependency_interfaces={},\n"
        "        dependency_context={},\n"
        "        dependency_usage={},\n"
        "        vars={},\n"
        "        glossary='glossary text',\n"
        "        hint_code=({} if mode == 'hint' else None),\n"
        "    )\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion ' + component_id + ' ' + criterion_id)\n"
        "    return CriterionBundle(\n"
        "        component_id=component_id,\n"
        "        criterion_id=criterion_id,\n"
        "        covers='R-X-001',\n"
        "        criterion_text='Given When Then',\n"
        "        requirement_text='req',\n"
        "        interface='interface text',\n"
        "        glossary='glossary text',\n"
        "        dependency_interfaces={},\n"
        "    )\n"
    )


def _fake_generator(log_path):
    return (
        "from dataclasses import dataclass, field\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'generator@2.0.0'\n"
        "PROMPT_VERSION = 'v10'\n"
        "\n"
        + _LOG_HELPER +
        "@dataclass\n"
        "class GenerationResult:\n"
        "    component_id: str\n"
        "    spec_bundle_hash: str\n"
        "    model: str\n"
        "    prompt_version: str\n"
        "    cache_hit: bool\n"
        "    files: dict = field(default_factory=dict)\n"
        "    model_call_error: dict = None\n"
        "    refused: str = None\n"
        "    retry_feedback: list = None\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    cid = bundle['component_id'] if isinstance(bundle, dict) else bundle.component_id\n"
        "    h = bundle['spec_bundle_hash'] if isinstance(bundle, dict) else bundle.spec_bundle_hash\n"
        "    _log('generate ' + cid)\n"
        "    return GenerationResult(\n"
        "        component_id=cid,\n"
        "        spec_bundle_hash=h,\n"
        "        model=model,\n"
        "        prompt_version=PROMPT_VERSION,\n"
        "        cache_hit=False,\n"
        "        files={'module.py': 'x = 1\\n'},\n"
        "        model_call_error=None,\n"
        "        refused=None,\n"
        "        retry_feedback=retry_feedback,\n"
        "    )\n"
    )


def _fake_llm_endpoint(log_path):
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        + _LOG_HELPER +
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('complete')\n"
        "    if backend is not None:\n"
        "        return backend(prompt, model, **params)\n"
        "    return {'text': '{}', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    )


def test_predicted_blast_radius_lists_exactly_impact_analyzer_components(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    lint_log = log_dir / "lint.log"
    impact_log = log_dir / "impact.log"
    assemble_log = log_dir / "assemble.log"
    generate_log = log_dir / "generate.log"
    endpoint_log = log_dir / "endpoint.log"

    gen = repo_root / "gen"
    _write(gen / "spec-linter" / "spec_linter.py", _fake_spec_linter(lint_log, _real_linter_path()))
    _write(gen / "impact-analyzer" / "impact_analyzer.py", _fake_impact_analyzer(impact_log))
    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _fake_spec_bundle_assembler(assemble_log),
    )
    _write(gen / "generator" / "generator.py", _fake_generator(generate_log))
    _write(gen / "llm-endpoint" / "llm_endpoint.py", _fake_llm_endpoint(endpoint_log))

    report = spec_completeness_assistant.assist(["R-ALPHA-001"], repo_root)

    # The faked impact-analyzer was actually consulted.
    assert impact_log.is_file()
    assert "compute_blast_radius" in impact_log.read_text(encoding="utf-8")

    radius = field(report, "predicted_blast_radius")
    ids = []
    for entry in radius:
        if isinstance(entry, str):
            ids.append(entry)
        else:
            ids.append(field(entry, "component_id"))

    assert len(ids) == 2
    assert sorted(ids) == ["comp-alpha", "comp-beta"]