# hotdocs-criterion: sha256:2cde0f4f7e0bd43a63df1ab1e2eb658d75558ea2f6b8a6650b86b752923dd3f7
"""CS-ZERO-EDIT-001 (covers P-ZERO-EDIT).

Given a ratified, non-sealed component spec bundle with complete,
agent-checkable acceptance criteria, when a spec change goes through the
pipeline, then the resulting gen/<component>/ passes every gate with zero
commits to gen/<component>/ authored by a human between the spec merge and
the pipeline's own merge commit.

The test plays the human only up to the spec merge commit.  From then on
only the pipeline (``component_gate_runner.run_component_gates`` driving the
real ``generation-loop`` and real ``generator``, with an injected mock model)
touches the working tree; the test then makes the pipeline's merge commit and
checks the git history of gen/<component>/.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import component_gate_runner


HUMAN_NAME = "Spec Author"
HUMAN_EMAIL = "human@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@example.invalid"

COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODEL = "mock-model"

WIDGET_SOURCE = "def add(a, b):\n    return a + b\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# Synthetic spec corpus
# --------------------------------------------------------------------------

def build_corpus(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "last_ratified_commit: 0000000\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Adds two integers.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n`add(a, b)` MUST return the sum `a + b`.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the integers 2 and 3\n"
        "When add is called with them\n"
        "Then the result is 5\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\nOne module file, `widget.py`.\n\n```\nadd(a: int, b: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nPure function, no I/O.\n")
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** - adds numbers.\n")


# --------------------------------------------------------------------------
# Fake dependencies (flat-module shape under <repo_root>/gen/<slug>/)
# --------------------------------------------------------------------------

FAKE_ASSEMBLER = (
    "import hashlib\n"
    "from collections.abc import Mapping\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "class SpecBundle(Mapping):\n"
    "    _FIELDS = ('component_id', 'spec_bundle_hash', 'spec', 'interface', 'constraints',\n"
    "               'dependency_interfaces', 'dependency_context', 'dependency_usage',\n"
    "               'vars', 'glossary', 'hint_code', 'spec_bundle_parts')\n"
    "\n"
    "    def __init__(self, **kwargs):\n"
    "        for name in self._FIELDS:\n"
    "            setattr(self, name, kwargs.get(name))\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        if key not in self._FIELDS:\n"
    "            raise KeyError(key)\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def __iter__(self):\n"
    "        return iter(self._FIELDS)\n"
    "\n"
    "    def __len__(self):\n"
    "        return len(self._FIELDS)\n"
    "\n"
    "\n"
    "def _read(path):\n"
    "    path = Path(path)\n"
    "    return path.read_text(encoding='utf-8').strip() if path.is_file() else ''\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
    "    comp = Path(repo_root) / 'specs' / 'components' / slug\n"
    "    spec_parts = [_read(comp / 'component.md')]\n"
    "    for p in sorted((comp / 'requirements').glob('*.md')):\n"
    "        spec_parts.append(_read(p))\n"
    "    spec = '\\n\\n'.join(x for x in spec_parts if x)\n"
    "    interface = '\\n\\n'.join(x for x in (_read(p) for p in sorted((comp / 'interface').rglob('*.md'))) if x)\n"
    "    constraints = _read(comp / 'constraints.md')\n"
    "    glossary = _read(Path(repo_root) / 'specs' / 'glossary.md')\n"
    "    spec_hash = 'sha256:' + hashlib.sha256((spec + interface + constraints).encode('utf-8')).hexdigest()\n"
    "    dep_hash = 'sha256:' + hashlib.sha256(b'').hexdigest()\n"
    "    total = 'sha256:' + hashlib.sha256((spec_hash + dep_hash).encode('utf-8')).hexdigest()\n"
    "    hint = None\n"
    "    if mode == 'hint':\n"
    "        hint = {}\n"
    "    return SpecBundle(component_id=component_id, spec_bundle_hash=total, spec=spec,\n"
    "                      interface=interface, constraints=constraints,\n"
    "                      dependency_interfaces={}, dependency_context={}, dependency_usage={},\n"
    "                      vars={}, glossary=glossary, hint_code=hint,\n"
    "                      spec_bundle_parts={'spec': spec_hash, 'dependency_code': dep_hash})\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    bundle = assemble(component_id, repo_root)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-WIDGET-001', 'criterion_text': '',\n"
    "            'requirement_text': '', 'interface': bundle['interface'],\n"
    "            'glossary': bundle['glossary'], 'dependency_interfaces': {}, 'testing': ''}\n"
)


def fake_provenance_checker(log_path):
    return (
        "import sys\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "sys.path.insert(0, " + repr("") + ") if False else None\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "\n"
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, spec_bundle_parts, gate_versions, assets, drivers):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.spec_bundle_parts = spec_bundle_parts\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "        self.drivers = drivers\n"
        "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key ' + component_id)\n"
        "    return None\n"
        "\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key ' + component_id)\n"
        "    return ProvenanceKey(\n"
        "        'sha256:' + 'ab' * 32,\n"
        "        {'spec': 'sha256:' + 'cd' * 32, 'dependency_code': 'sha256:' + 'ef' * 32},\n"
        "        {'compiler': 'criterion-compiler@1.0.0',\n"
        "         'generated_test': 'generated_test@3.0.0',\n"
        "         'verifier': 'verifier-orchestrator@4.0.0',\n"
        "         'license_scanner': 'license_scanner@4.0.3+fake',\n"
        "         'secret_scanner': 'secret_scanner@0.0.0',\n"
        "         'generator': 'generator@3.2.0+v12'},\n"
        "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "          'adapter_sha256': 'sha256:' + '00' * 32, 'versions': {'python': '3'},\n"
        "          'lockfile_sha256': None}],\n"
        "        [])\n"
        "\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance ' + component_id)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )


def fake_surface_checker(log_path):
    return (
        "from pathlib import Path\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
        "    base = Path(code_dir) if code_dir is not None else Path(repo_root) / 'gen' / slug\n"
        "    ok = (base / 'widget.py').is_file()\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('check_surface ' + component_id + ' ' + str(ok) + '\\n')\n"
        "    findings = [] if ok else [{'kind': 'import_error', 'message': 'widget.py missing'}]\n"
        "    return {'ok': ok, 'findings': findings}\n"
    )


def fake_verifier(log_path):
    return (
        "import importlib.util\n"
        "import sys\n"
        "from pathlib import Path\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "\n"
        "def _check(path):\n"
        "    if not path.is_file():\n"
        "        return False\n"
        "    previous = sys.dont_write_bytecode\n"
        "    sys.dont_write_bytecode = True\n"
        "    name = 'zero_edit_widget_under_test'\n"
        "    try:\n"
        "        spec = importlib.util.spec_from_file_location(name, path)\n"
        "        module = importlib.util.module_from_spec(spec)\n"
        "        sys.modules[name] = module\n"
        "        spec.loader.exec_module(module)\n"
        "        return module.add(2, 3) == 5 and module.add(-4, 4) == 0 and module.add(10, 7) == 17\n"
        "    except Exception:\n"
        "        return False\n"
        "    finally:\n"
        "        sys.modules.pop(name, None)\n"
        "        sys.dont_write_bytecode = previous\n"
        "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
        "    ok = _check(Path(repo_root) / 'gen' / slug / 'widget.py')\n"
        "    result = 'pass' if ok else 'fail'\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('verify ' + component_id + ' ' + result + '\\n')\n"
        "    criterion = {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001',\n"
        "                 'kind': 'generated-test', 'result': result}\n"
        "    if not ok:\n"
        "        criterion['failure_detail'] = {'message': 'add(2, 3) equals 5 failed',\n"
        "                                       'expected': 5, 'actual': None}\n"
        "        criterion['failure_origin'] = 'implementation'\n"
        "    return {'component_id': component_id, 'criteria': [criterion],\n"
        "            'requirement_results': {'R-WIDGET-001': result},\n"
        "            'interface_drift': False,\n"
        "            'mutation_score': 1.0 if ok else None, 'mutation_error': None,\n"
        "            'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                        'adapter_sha256': 'sha256:' + '00' * 32,\n"
        "                        'versions': {'python': '3'}, 'lockfile_sha256': None}],\n"
        "            'drivers': [], 'overall': result}\n"
    )


def fake_license_scanner(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.3+fake'\n"
        "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('license_scan ' + component_id + '\\n')\n"
        "    return {'component_id': component_id, 'gate_version': 'license_scanner@4.0.3+fake',\n"
        "            'similarity_score': 0.0, 'blocked': False, 'matches': []}\n"
    )


def fake_secret_scanner(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
        "\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('secret_scan\\n')\n"
        "    return {'scope': 'repo', 'gate_version': 'secret_scanner@0.0.0',\n"
        "            'flagged': False, 'matches': []}\n"
    )


def fake_provenance_writer(log_path):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class MissingInputError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "class InvalidSealedInputError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "def _f(value, name):\n"
        "    if isinstance(value, dict):\n"
        "        return value.get(name)\n"
        "    return getattr(value, name, None)\n"
        "\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
        "    gen_result = _f(inputs, 'generation_result')\n"
        "    report = _f(inputs, 'verification_report')\n"
        "    files = _f(gen_result, 'files') or {}\n"
        "    if files and report is None:\n"
        "        raise MissingInputError('verification_report')\n"
        "    manifest = {\n"
        "        'spec_bundle_hash': _f(gen_result, 'spec_bundle_hash'),\n"
        "        'model_pin': _f(gen_result, 'model'),\n"
        "        'files': sorted(files),\n"
        "        'overall': _f(report, 'overall') if report is not None else None,\n"
        "        'provenance_hit': False,\n"
        "    }\n"
        "    text = json.dumps(manifest, sort_keys=True)\n"
        "    for base in (Path(repo_root) / 'gen' / slug, Path(repo_root) / 'verification' / slug):\n"
        "        base.mkdir(parents=True, exist_ok=True)\n"
        "        (base / '.provenance.json').write_text(text, encoding='utf-8')\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('write_provenance ' + component_id + '\\n')\n"
        "\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    raise InvalidSealedInputError('not sealed in this fixture')\n"
    )


def fake_provenance_tracker(log_path):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    base = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
        "    base.mkdir(parents=True, exist_ok=True)\n"
        "    n = len(list(base.iterdir())) + 1\n"
        "    (base / (str(n) + '.json')).write_text(json.dumps({'spec_bundle_hash': spec_bundle_hash}),\n"
        "                                           encoding='utf-8')\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('write_attempt_record ' + component_id + '\\n')\n"
    )


FAKE_KIND_PYTHON = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "KIND = 'python'\n"
    "GATE_VERSION = 'kind-python@1.0.0'\n"
    "\n"
    "\n"
    "class AssetError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "def layout_errors(asset_file):\n"
    "    return []\n"
    "\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {'names': []}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '',\n"
    "            'versions': {'python': sys.version.split()[0], 'packages': 'sha256:' + '00' * 32},\n"
    "            'lockfile_sha256': None, 'interpreter': sys.executable}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    def run(name, args):\n"
    "        raise AssetError('not supported in this fixture')\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return []\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    return None\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {'generator': '', 'test_author': ''}\n"
)


def build_fakes(repo_root, log_path):
    gen = repo_root / "gen"
    write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", FAKE_ASSEMBLER)
    write(gen / "provenance-checker" / "provenance_checker.py", fake_provenance_checker(log_path))
    write(gen / "surface-checker" / "surface_checker.py", fake_surface_checker(log_path))
    write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", fake_verifier(log_path))
    write(gen / "license-scanner" / "license_scanner.py", fake_license_scanner(log_path))
    write(gen / "secret-scanner" / "secret_scanner.py", fake_secret_scanner(log_path))
    write(gen / "provenance-writer" / "provenance_writer.py", fake_provenance_writer(log_path))
    write(gen / "provenance-tracker" / "provenance_tracker.py", fake_provenance_tracker(log_path))
    write(gen / "kind-python" / "kind_python.py", FAKE_KIND_PYTHON)


# --------------------------------------------------------------------------
# git helpers
# --------------------------------------------------------------------------

def git(repo_root, home, *args, author=None):
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    if author is not None:
        name, email = author
        env["GIT_AUTHOR_NAME"] = name
        env["GIT_AUTHOR_EMAIL"] = email
        env["GIT_COMMITTER_NAME"] = name
        env["GIT_COMMITTER_EMAIL"] = email
    cmd = ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args)
    done = subprocess.run(cmd, cwd=str(repo_root), env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


# --------------------------------------------------------------------------
# The test
# --------------------------------------------------------------------------

def test_spec_change_merges_with_zero_human_edits_to_gen(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git is required to inspect commit authorship")

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    log_path = tmp_path / "fake-calls.log"
    log_path.write_text("", encoding="utf-8")

    monkeypatch.chdir(repo_root)

    human = (HUMAN_NAME, HUMAN_EMAIL)
    pipeline = (PIPELINE_NAME, PIPELINE_EMAIL)

    git(repo_root, home, "init", "-q")

    # Tooling the pipeline runs on (not gen/<component>/).
    build_fakes(repo_root, log_path)
    write(repo_root / ".gitignore", ".hotdocs/\n__pycache__/\n")
    git(repo_root, home, "add", "-A")
    git(repo_root, home, "commit", "-q", "-m", "tooling", author=human)

    # The human's spec merge: a ratified, non-sealed component with
    # complete, agent-checkable acceptance criteria.
    build_corpus(repo_root)
    git(repo_root, home, "add", "specs")
    git(repo_root, home, "commit", "-q", "-m", "spec merge: comp-widget", author=human)
    spec_merge = git(repo_root, home, "rev-parse", "HEAD").strip()

    target_dir = repo_root / "gen" / SLUG
    assert not target_dir.exists(), "no gen/<component>/ may exist before the pipeline runs"

    model_calls = []

    def backend(prompt, model, **params):
        model_calls.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        assert match is not None, "generator prompt must state this call's nonce"
        nonce = match.group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget.py-----\n"
            + WIDGET_SOURCE
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    # The pipeline, and only the pipeline, acts from here on.
    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, MODEL, 0, backend
    )

    # Every gate passes.
    assert field(result, "component_id") == COMPONENT_ID
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False, field(result, "block_reason")
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
    for criterion in field(verification, "criteria"):
        assert field(criterion, "result") == "pass"
    assert field(field(result, "license_scan"), "blocked") is False
    assert field(field(result, "secret_scan"), "flagged") is False
    attempts = field(result, "attempts")
    assert len(attempts) >= 1
    assert field(attempts[-1], "outcome") == "passed"

    # The code was produced by the pipeline from the model's reply.
    assert len(model_calls) >= 1
    produced = target_dir / "widget.py"
    assert produced.is_file()
    assert produced.read_text(encoding="utf-8") == WIDGET_SOURCE

    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert "verify " + COMPONENT_ID + " pass" in log_lines
    assert "license_scan " + COMPONENT_ID in log_lines
    assert "secret_scan" in log_lines
    assert "write_provenance " + COMPONENT_ID in log_lines

    # The pipeline's own merge commit.
    git(repo_root, home, "add", "-A", "gen", "verification")
    git(repo_root, home, "commit", "-q", "-m", "pipeline merge: comp-widget", author=pipeline)
    pipeline_merge = git(repo_root, home, "rev-parse", "HEAD").strip()
    assert pipeline_merge != spec_merge

    # Zero commits to gen/<component>/ authored by a human between the
    # spec merge and the pipeline's merge commit.
    history = git(
        repo_root, home, "log", "--format=%H%x09%an%x09%ae",
        spec_merge + ".." + pipeline_merge, "--", "gen/" + SLUG,
    ).splitlines()
    assert history, "the pipeline merge commit must carry gen/<component>/"
    human_commits = [line for line in history if line.split("\t")[1:] != [PIPELINE_NAME, PIPELINE_EMAIL]]
    assert human_commits == []
    assert any(line.split("\t")[0] == pipeline_merge for line in history)

    # And nothing in gen/<component>/ was touched before the spec merge.
    before = git(repo_root, home, "log", "--format=%H", spec_merge, "--", "gen/" + SLUG).splitlines()
    assert before == []

    # The committed tree is exactly what the pipeline produced.
    committed = git(repo_root, home, "show", pipeline_merge + ":gen/" + SLUG + "/widget.py")
    assert committed == WIDGET_SOURCE