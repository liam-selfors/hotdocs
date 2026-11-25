# hotdocs-criterion: sha256:c07e87e212f56a9ea9e110d616a19c654fa2e114a01b526f29c9028d4e37f379
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import component_gate_runner


HUMAN_NAME = "Human Developer"
HUMAN_EMAIL = "human@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@hotdocs.invalid"

SPEC_HASH = "sha256:" + "a" * 64
GENERATED_SOURCE = "def widget():\n    return 'widget'\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args, name=HUMAN_NAME, email=HUMAN_EMAIL):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    cmd = [
        "git",
        "-c", "user.name=" + name,
        "-c", "user.email=" + email,
        "-c", "commit.gpgsign=false",
        "-c", "init.defaultBranch=main",
    ] + list(args)
    proc = subprocess.run(cmd, cwd=str(repo), env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def log_prelude(log_path):
    return (
        "import json\n"
        "import os\n"
        "from pathlib import Path\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(name, payload):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': name, 'args': payload}, default=str) + '\\n')\n"
    )


def build_fakes(repo, log_path):
    prelude = log_prelude(log_path)

    write(repo / "gen" / "provenance-checker" / "provenance_checker.py", prelude + (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr(SPEC_HASH) + "\n"
        "        self.gate_versions = {\n"
        "            'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@3.0.0',\n"
        "            'verifier': 'verifier-orchestrator@3.5.0',\n"
        "            'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "            'generator': 'generator@3.2.0+v12',\n"
        "        }\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                        'adapter_sha256': 'sha256:' + 'b' * 64,\n"
        "                        'versions': {'python': '3.12.4', 'packages': 'sha256:' + 'c' * 64},\n"
        "                        'lockfile_sha256': None}]\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', [component_id])\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', [component_id])\n"
        "    return _Key()\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', [component_id, spec_bundle_hash])\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    write(repo / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", prelude + (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', [component_id, mode])\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': " + repr(SPEC_HASH) + ",\n"
        "            'spec': 'SPEC', 'interface': 'IFACE', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': 'R-WIDGET-001', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    ))

    write(repo / "gen" / "generation-loop" / "generation_loop.py", prelude + (
        "GENERATED = " + repr(GENERATED_SOURCE) + "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', [component_id, model, mode, max_attempts])\n"
        "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
        "    target = Path(repo_root) / 'gen' / slug\n"
        "    target.mkdir(parents=True, exist_ok=True)\n"
        "    (target / (slug.replace('-', '_') + '.py')).write_text(GENERATED, encoding='utf-8')\n"
        "    generation_result = {\n"
        "        'component_id': component_id, 'spec_bundle_hash': bundle['spec_bundle_hash'],\n"
        "        'model': model, 'prompt_version': 'v12', 'cache_hit': False,\n"
        "        'files': {slug.replace('-', '_') + '.py': GENERATED},\n"
        "        'model_call_error': None, 'refused': None, 'retry_feedback': retry_feedback,\n"
        "        'mode': mode, 'transcript_sha256': None, 'turns': 1, 'tool_calls': 0,\n"
        "        'isolation': None}\n"
        "    verification_report = {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [{'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001',\n"
        "                      'kind': 'generated-test', 'result': 'pass'}],\n"
        "        'requirement_results': {'R-WIDGET-001': 'pass'},\n"
        "        'interface_drift': False, 'mutation_score': 1.0, 'mutation_error': None,\n"
        "        'assets': [], 'overall': 'pass'}\n"
        "    surface_report = {'ok': True, 'findings': []}\n"
        "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
        "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
        "               'failed_requirements': [], 'transcript_sha256': None,\n"
        "               'reauthored_tests': []}\n"
        "    if on_attempt is not None:\n"
        "        on_attempt(attempt, generation_result, verification_report)\n"
        "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [attempt],\n"
        "            'generation_result': generation_result,\n"
        "            'verification_report': verification_report,\n"
        "            'surface_report': surface_report}\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': 'ok'}\n"
        "    return (test_author, judge)\n"
    ))

    write(repo / "gen" / "provenance-tracker" / "provenance_tracker.py", prelude + (
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', [component_id, spec_bundle_hash])\n"
        "    return None\n"
    ))

    write(repo / "gen" / "license-scanner" / "license_scanner.py", prelude + (
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.3+9f2c41ab07de'\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', [component_id])\n"
        "    return {'component_id': component_id,\n"
        "            'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "            'similarity_score': 0.0, 'blocked': False, 'matches': []}\n"
    ))

    write(repo / "gen" / "secret-scanner" / "secret_scanner.py", prelude + (
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan', [])\n"
        "    return {'scope': 'repository', 'gate_version': 'secret_scanner@0.0.0',\n"
        "            'flagged': False, 'matches': []}\n"
    ))

    write(repo / "gen" / "provenance-writer" / "provenance_writer.py", prelude + (
        "def _plain(value):\n"
        "    return json.loads(json.dumps(value, default=lambda o: getattr(o, '__dict__', str(o))))\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', [component_id])\n"
        "    slug = component_id[len('comp-'):]\n"
        "    gr = inputs['generation_result']\n"
        "    manifest = {\n"
        "        'spec_bundle_hash': gr['spec_bundle_hash'], 'model_pin': gr['model'],\n"
        "        'prompt_version': gr['prompt_version'], 'retry_feedback': gr['retry_feedback'],\n"
        "        'generation': {'mode': gr['mode'], 'generator_version': 'generator@3.2.0+v12',\n"
        "                       'transcript_sha256': None, 'turns': 1, 'tool_calls': 0,\n"
        "                       'isolation': None},\n"
        "        'attempts': inputs['attempts'],\n"
        "        'attempt_history': _plain(inputs.get('attempt_history', [])),\n"
        "        'pipeline_version': 'v1', 'gate_versions': _plain(inputs['gate_versions']),\n"
        "        'provenance_hit': inputs['provenance_hit'],\n"
        "        'generated_at': '2026-01-01T00:00:00Z', 'verification_run_id': 'run-1',\n"
        "        'verification_report': _plain(inputs['verification_report']),\n"
        "        'license_scan': _plain(inputs['license_scan_result']),\n"
        "        'secret_scan': _plain(inputs['secret_scan_result']),\n"
        "        'assets': []}\n"
        "    for base in (Path(repo_root) / 'gen' / slug, Path(repo_root) / 'verification' / slug):\n"
        "        base.mkdir(parents=True, exist_ok=True)\n"
        "        (base / '.provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', [component_id])\n"
        "    return None\n"
    ))


def build_corpus(repo):
    write(repo / "specs" / "components" / "widget" / "component.md", (
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Returns a widget.\n"
    ))
    write(repo / "specs" / "components" / "widget" / "requirements" / "R-WIDGET-001.md", (
        "# R-WIDGET-001\n"
        "\n"
        "`widget()` MUST return the string `widget`.\n"
    ))
    write(repo / "specs" / "components" / "widget" / "acceptance" / "AC-WIDGET-001.md", (
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the widget module\n"
        "When widget() is called\n"
        "Then the result is \"widget\"\n"
        "```\n"
    ))
    write(repo / "specs" / "components" / "widget" / "interface" / "library.md", (
        "# Library\n"
        "\n"
        "```\n"
        "widget() -> str\n"
        "```\n"
    ))
    write(repo / "specs" / "components" / "widget" / "constraints.md", "# Constraints\n\nNone.\n")


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mock_backend(prompt, model, **params):
    return {"text": "", "model": model, "backend": "mock", "model_call_error": None}


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_cs_zero_edit_001_pipeline_merge_needs_no_human_edit_to_gen(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    log_path = logs / "calls.log"

    git(repo, "init", "-q")
    build_fakes(repo, log_path)
    build_corpus(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "setup")

    # A human merges a spec change (the spec merge).
    req = repo / "specs" / "components" / "widget" / "requirements" / "R-WIDGET-001.md"
    req.write_text(
        "# R-WIDGET-001\n\n`widget()` MUST return the string `widget`, and nothing else.\n",
        encoding="utf-8",
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "spec change")
    spec_merge = git(repo, "rev-parse", "HEAD").strip()

    assert not (repo / "gen" / "widget").exists()

    # The pipeline runs: generation, verification, scans, provenance.
    result = component_gate_runner.run_component_gates(
        "comp-widget", repo, "mock-model", seed=0, llm_backend=mock_backend,
    )

    # Every gate passes, with no human intervention.
    assert field(result, "component_id") == "comp-widget"
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    assert field(field(result, "verification"), "overall") == "pass"
    assert field(field(result, "license_scan"), "blocked") is not True
    assert field(field(result, "secret_scan"), "flagged") is not True

    calls = [entry["call"] for entry in read_log(log_path)]
    assert calls.count("run_attempts") == 1
    assert "license_scan" in calls
    assert "secret_scan" in calls
    assert "write_provenance" in calls

    generated = repo / "gen" / "widget" / "widget.py"
    assert generated.read_text(encoding="utf-8") == GENERATED_SOURCE
    manifest = json.loads((repo / "gen" / "widget" / ".provenance.json").read_text(encoding="utf-8"))
    assert manifest["verification_report"]["overall"] == "pass"
    assert manifest["license_scan"]["blocked"] is False
    assert manifest["secret_scan"]["flagged"] is False

    # The pipeline commits its own output: its merge commit.
    git(repo, "add", "-A", name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    git(repo, "commit", "-q", "-m", "pipeline merge", name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    pipeline_merge = git(repo, "rev-parse", "HEAD").strip()
    assert pipeline_merge != spec_merge

    # Nothing under gen/widget/ is left for a human to touch.
    assert git(repo, "status", "--porcelain", "--", "gen/widget").strip() == ""

    authors = [
        line for line in git(
            repo, "log", "--format=%an|%ae",
            spec_merge + ".." + pipeline_merge, "--", "gen/widget",
        ).splitlines() if line.strip()
    ]
    assert authors, "the pipeline's merge commit must touch gen/widget/"
    assert all(line == PIPELINE_NAME + "|" + PIPELINE_EMAIL for line in authors), authors
    assert not any(HUMAN_EMAIL in line for line in authors)

    committed = git(repo, "show", pipeline_merge + ":gen/widget/widget.py")
    assert committed == GENERATED_SOURCE