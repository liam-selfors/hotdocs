# hotdocs-criterion: sha256:96e1314fa8caf490b7f89037b0a8cdfe5d5679cc0419453d6666da871bc7bdc5
"""CS-ZERO-EDIT-001: a ratified, non-sealed component's spec change goes
through the pipeline and lands with zero human-authored commits to
gen/<component>/ between the spec merge and the pipeline's own merge commit.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import component_gate_runner


HUMAN_NAME = "Spec Author"
HUMAN_EMAIL = "spec-author@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@hotdocs.invalid"

COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE = "widget"
SPEC_HASH = "sha256:" + "ab" * 32
GENERATED_FILES = {"widget.py": "def widget():\n    return 42\n"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args, name=None, email=None):
    cmd = ["git"]
    if name is not None:
        cmd += ["-c", "user.name=" + name, "-c", "user.email=" + email]
    cmd += ["-c", "commit.gpgsign=false"]
    cmd += list(args)
    proc = subprocess.run(
        cmd, cwd=str(repo_root), capture_output=True, text=True, check=True
    )
    return proc.stdout


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


LOG_HELPER = (
    "import json\n"
    "def _log(name, payload):\n"
    "    with open(LOG, 'a') as fh:\n"
    "        fh.write(json.dumps({'call': name, 'args': payload}, default=str) + '\\n')\n"
    "def _get(value, name):\n"
    "    if isinstance(value, dict):\n"
    "        return value.get(name)\n"
    "    return getattr(value, name, None)\n"
)


PROVENANCE_CHECKER_BODY = (
    "GATE_VERSIONS = {\n"
    "    'compiler': 'criterion-compiler@1.0.0',\n"
    "    'generated_test': 'generated_test@3.0.0',\n"
    "    'verifier': 'verifier-orchestrator@3.5.0',\n"
    "    'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
    "    'secret_scanner': 'secret_scanner@0.0.0',\n"
    "    'generator': 'generator@3.2.0+v12',\n"
    "}\n"
    "ASSETS = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "           'adapter_sha256': 'sha256:' + '00' * 32,\n"
    "           'versions': {'python': '3.14.6', 'packages': 'sha256:' + '11' * 32},\n"
    "           'lockfile_sha256': None}]\n"
    "class _Key:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', {'component_id': component_id})\n"
    "    return None\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', {'component_id': component_id})\n"
    "    return _Key(SPEC_HASH, dict(GATE_VERSIONS), list(ASSETS))\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', {'component_id': component_id,\n"
    "                              'spec_bundle_hash': spec_bundle_hash})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', {'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


ASSEMBLER_BODY = (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', {'component_id': component_id, 'mode': mode})\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': SPEC_HASH,\n"
    "            'spec': 'SPEC', 'interface': 'IFACE', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
    "            'hint_code': None}\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', {'component_id': component_id,\n"
    "                                'criterion_id': criterion_id})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-WIDGET-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {},\n"
    "            'testing': ''}\n"
)


GENERATION_LOOP_BODY = (
    "from pathlib import Path\n"
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "class _LoopResult:\n"
    "    def __init__(self, passed, stop_reason, attempts, generation_result,\n"
    "                 verification_report, surface_report):\n"
    "        self.passed = passed\n"
    "        self.stop_reason = stop_reason\n"
    "        self.attempts = attempts\n"
    "        self.generation_result = generation_result\n"
    "        self.verification_report = verification_report\n"
    "        self.surface_report = surface_report\n"
    "    def to_dict(self):\n"
    "        return {'passed': self.passed, 'stop_reason': self.stop_reason,\n"
    "                'attempts': self.attempts,\n"
    "                'generation_result': self.generation_result,\n"
    "                'verification_report': self.verification_report,\n"
    "                'surface_report': self.surface_report}\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', {'model': model, 'seed': seed})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': 'ok'}\n"
    "    return (test_author, judge)\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    if mode not in ('single', 'agentic') or max_attempts < 1:\n"
    "        raise ValueError('bad arguments')\n"
    "    _log('run_attempts', {'component_id': component_id, 'model': model,\n"
    "                          'mode': mode, 'max_attempts': max_attempts,\n"
    "                          'bundle_component_id': _get(bundle, 'component_id')})\n"
    "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
    "    out = Path(repo_root) / 'gen' / slug\n"
    "    out.mkdir(parents=True, exist_ok=True)\n"
    "    for rel, content in FILES.items():\n"
    "        target = out / rel\n"
    "        target.parent.mkdir(parents=True, exist_ok=True)\n"
    "        target.write_text(content)\n"
    "    generation_result = {\n"
    "        'component_id': component_id, 'spec_bundle_hash': SPEC_HASH,\n"
    "        'model': model, 'prompt_version': 'v12', 'cache_hit': False,\n"
    "        'files': dict(FILES), 'model_call_error': None, 'refused': None,\n"
    "        'retry_feedback': retry_feedback, 'mode': mode,\n"
    "        'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
    "    verification_report = {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001',\n"
    "                      'kind': 'generated-test', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-WIDGET-001': 'pass'},\n"
    "        'interface_drift': False, 'mutation_score': 1.0, 'mutation_error': None,\n"
    "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                    'adapter_sha256': 'sha256:' + '00' * 32,\n"
    "                    'versions': {'python': '3.14.6'}, 'lockfile_sha256': None}],\n"
    "        'overall': 'pass'}\n"
    "    surface_report = {'ok': True, 'findings': []}\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, verification_report)\n"
    "    return _LoopResult(True, 'passed', [attempt], generation_result,\n"
    "                       verification_report, surface_report)\n"
)


TRACKER_BODY = (
    "from pathlib import Path\n"
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', {'component_id': component_id,\n"
    "                                  'spec_bundle_hash': spec_bundle_hash,\n"
    "                                  'overall': _get(verification_report, 'overall')})\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    n = len(list(d.iterdir())) + 1\n"
    "    (d / ('attempt-' + str(n) + '.json')).write_text(\n"
    "        json.dumps({'spec_bundle_hash': spec_bundle_hash}))\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


LICENSE_BODY = (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.3+9f2c41ab07de'\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', {'component_id': component_id})\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',\n"
    "            'similarity_score': 0.0, 'blocked': False, 'matches': []}\n"
)


SECRET_BODY = (
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan', {})\n"
    "    return {'scope': 'repo', 'gate_version': 'secret_scanner@0.0.0',\n"
    "            'flagged': False, 'matches': []}\n"
)


WRITER_BODY = (
    "from pathlib import Path\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "class InvalidSealedInputError(ValueError):\n"
    "    pass\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    gen_result = _get(inputs, 'generation_result')\n"
    "    report = _get(inputs, 'verification_report')\n"
    "    _log('write_provenance', {'component_id': component_id,\n"
    "                              'provenance_hit': _get(inputs, 'provenance_hit'),\n"
    "                              'overall': _get(report, 'overall'),\n"
    "                              'files': sorted((_get(gen_result, 'files') or {}).keys())})\n"
    "    if report is None and (_get(gen_result, 'files') or {}):\n"
    "        raise MissingInputError('verification_report')\n"
    "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
    "    manifest = {\n"
    "        'spec_bundle_hash': _get(gen_result, 'spec_bundle_hash'),\n"
    "        'model_pin': _get(gen_result, 'model'),\n"
    "        'prompt_version': _get(gen_result, 'prompt_version'),\n"
    "        'retry_feedback': _get(gen_result, 'retry_feedback'),\n"
    "        'attempts': _get(inputs, 'attempts'),\n"
    "        'attempt_history': _get(inputs, 'attempt_history') or [],\n"
    "        'gate_versions': _get(inputs, 'gate_versions'),\n"
    "        'provenance_hit': _get(inputs, 'provenance_hit'),\n"
    "        'verification_report': report,\n"
    "        'license_scan': _get(inputs, 'license_scan_result'),\n"
    "        'secret_scan': _get(inputs, 'secret_scan_result'),\n"
    "    }\n"
    "    text = json.dumps(manifest, default=str, sort_keys=True, indent=2) + '\\n'\n"
    "    for base in ('gen', 'verification'):\n"
    "        p = Path(repo_root) / base / slug / '.provenance.json'\n"
    "        p.parent.mkdir(parents=True, exist_ok=True)\n"
    "        p.write_text(text)\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', {'component_id': component_id})\n"
)


def write_fake(repo_root, slug, module, log_path, body, extra=""):
    source = (
        "LOG = " + repr(str(log_path)) + "\n"
        + "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
        + extra
        + LOG_HELPER
        + body
    )
    write(repo_root / "gen" / slug / (module + ".py"), source)


def build_fixture(repo_root, log_path):
    write(repo_root / ".gitignore", "__pycache__/\n*.pyc\n")
    write(
        repo_root / "specs" / "components" / SLUG / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "last_ratified_commit: 0000000\n"
        "depends_on: []\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\n"
        "Returns the widget number.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n`widget()` MUST return 42.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the widget module\n"
        "When widget() is called\n"
        "Then the result is 42\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "interface" / "library.md",
        "# Library\n\n```\nwidget() -> int\n```\n",
    )
    write(repo_root / "specs" / "components" / SLUG / "constraints.md", "# Constraints\n\nNone.\n")

    write_fake(repo_root, "provenance-checker", "provenance_checker", log_path,
               PROVENANCE_CHECKER_BODY)
    write_fake(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", log_path,
               ASSEMBLER_BODY)
    write_fake(repo_root, "generation-loop", "generation_loop", log_path,
               GENERATION_LOOP_BODY, extra="FILES = " + repr(GENERATED_FILES) + "\n")
    write_fake(repo_root, "provenance-tracker", "provenance_tracker", log_path, TRACKER_BODY)
    write_fake(repo_root, "license-scanner", "license_scanner", log_path, LICENSE_BODY)
    write_fake(repo_root, "secret-scanner", "secret_scanner", log_path, SECRET_BODY)
    write_fake(repo_root, "provenance-writer", "provenance_writer", log_path, WRITER_BODY)


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_cs_zero_edit_001_pipeline_merge_has_no_human_commits_to_gen(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required for this capability scenario")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    git(repo_root, "init", "-q")
    build_fixture(repo_root, log_path)

    # The human-authored, ratified spec change is merged.
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "Merge spec change for comp-widget",
        name=HUMAN_NAME, email=HUMAN_EMAIL)
    spec_merge = git(repo_root, "rev-parse", "HEAD").strip()
    assert not (repo_root / "gen" / SLUG).exists()

    # The pipeline runs: generation -> verification -> scans -> provenance.
    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "mock:model", seed=0
    )

    calls = [entry["call"] for entry in read_log(log_path)]
    assert "current_sealed_key" in calls
    assert "run_attempts" in calls
    assert "license_scan" in calls
    assert "secret_scan" in calls
    assert "write_provenance" in calls

    # Every gate passes, with nothing for a human to fix.
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    verification = field(result, "verification")
    assert field(verification, "overall") == "pass"
    for criterion in field(verification, "criteria"):
        assert field(criterion, "result") == "pass"
    assert field(field(result, "license_scan"), "blocked") is False
    assert field(field(result, "secret_scan"), "flagged") is False

    # gen/<component>/ holds exactly what the pipeline produced.
    for rel, content in GENERATED_FILES.items():
        assert (repo_root / "gen" / SLUG / rel).read_text() == content
    manifest = json.loads((repo_root / "gen" / SLUG / ".provenance.json").read_text())
    assert manifest["provenance_hit"] is False
    assert manifest["verification_report"]["overall"] == "pass"
    assert manifest["spec_bundle_hash"] == SPEC_HASH

    # The pipeline's own merge commit.
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "hotdocs: regenerate comp-widget",
        name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    pipeline_merge = git(repo_root, "rev-parse", "HEAD").strip()
    assert pipeline_merge != spec_merge

    # Nothing left uncommitted under gen/<component>/.
    assert git(repo_root, "status", "--porcelain", "--", "gen/" + SLUG).strip() == ""

    # Every commit touching gen/<component>/ between the spec merge and the
    # pipeline's merge commit is the pipeline's; none is human-authored.
    lines = [
        line for line in git(
            repo_root, "log", "--format=%H\t%ae",
            spec_merge + ".." + pipeline_merge, "--", "gen/" + SLUG,
        ).splitlines() if line.strip()
    ]
    touching = [line.split("\t") for line in lines]
    assert touching, "the pipeline's merge commit should touch gen/" + SLUG
    human = [sha for sha, email in touching if email != PIPELINE_EMAIL]
    assert human == []
    assert [sha for sha, _ in touching] == [pipeline_merge]