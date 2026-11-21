# hotdocs-criterion: sha256:2755ce41321917b666e245a9389c737e601e6ff3b01bf26f51701e8cebdc1711
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import agentic_generator
import cache_manager
import capability_scenario_verifier
import component_gate_runner
import criterion_compiler
import generation_loop
import generator
import graph_query_engine
import hotdocs_cli
import hotdocs_init
import impact_analyzer
import kind_javascript
import kind_python
import llm_endpoint
import llm_tool_endpoint
import provenance_checker
import provenance_writer
import review_packet_builder
import spec_bundle_assembler
import surface_checker
import test_author
import test_probe
import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODEL = "claude-sonnet-5"

HUMAN_NAME = "Spec Author"
HUMAN_EMAIL = "spec-author@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@example.invalid"

WIDGET_SRC = "def widget(x):\n    return x * 2\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo, args, name, email):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    cmd = [
        "git",
        "-c", "user.name=" + name,
        "-c", "user.email=" + email,
        "-c", "commit.gpgsign=false",
    ] + list(args)
    proc = subprocess.run(
        cmd, cwd=str(repo), env=env, capture_output=True, text=True, check=True
    )
    return proc.stdout


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_prelude(log_path):
    return (
        "import json\n"
        "import os\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(fn, payload):\n"
        "    entry = dict(payload)\n"
        "    entry['fn'] = fn\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry, default=str) + '\\n')\n"
    )


def _fake_generator(log_path):
    return (
        _log_prelude(log_path)
        + "GATE_VERSION = 'generator@3.2.0'\n"
        "PROMPT_VERSION = 'v12'\n"
        "WIDGET_SRC = " + repr(WIDGET_SRC) + "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generate', {'component_id': bundle['component_id'], 'model': model,\n"
        "                      'retry_feedback': retry_feedback})\n"
        "    files = {'widget.py': WIDGET_SRC}\n"
        "    if bundle['hint_code'] is None:\n"
        "        out = os.path.join(str(repo_root), 'gen', " + repr(SLUG) + ")\n"
        "        os.makedirs(out, exist_ok=True)\n"
        "        for rel in files:\n"
        "            with open(os.path.join(out, rel), 'w', encoding='utf-8') as f:\n"
        "                f.write(files[rel])\n"
        "    return {\n"
        "        'component_id': bundle['component_id'],\n"
        "        'spec_bundle_hash': bundle['spec_bundle_hash'],\n"
        "        'model': model,\n"
        "        'prompt_version': PROMPT_VERSION,\n"
        "        'cache_hit': False,\n"
        "        'files': files,\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "        'mode': 'single',\n"
        "        'transcript_sha256': None,\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "    }\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log('commit_cache', {})\n"
        "def check_write_allowed(bundle, repo_root=None):\n"
        "    return None\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    return [('Spec', bundle['spec'])]\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    _log('write_files', {'component_id': component_id})\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    return (None, [])\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    return (None, [])\n"
    )


def _fake_surface_checker(log_path):
    return (
        _log_prelude(log_path)
        + "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log('check_surface', {'component_id': component_id})\n"
        "    return {'ok': True, 'findings': []}\n"
    )


def _fake_verifier(log_path):
    return (
        _log_prelude(log_path)
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', {'component_id': component_id})\n"
        "    path = os.path.join(str(repo_root), 'gen', " + repr(SLUG) + ", 'widget.py')\n"
        "    ok = False\n"
        "    if os.path.isfile(path):\n"
        "        with open(path, encoding='utf-8') as f:\n"
        "            ok = 'def widget' in f.read()\n"
        "    result = 'pass' if ok else 'fail'\n"
        "    criterion = {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001',\n"
        "                 'kind': 'compiled', 'result': result}\n"
        "    if not ok:\n"
        "        criterion['failure_detail'] = {'message': 'widget missing', 'expected': None, 'actual': None}\n"
        "        criterion['failure_origin'] = 'implementation'\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [criterion],\n"
        "        'requirement_results': {'R-WIDGET-001': result},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 1.0 if ok else None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                    'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
        "                    'lockfile_sha256': None}],\n"
        "        'overall': result,\n"
        "    }\n"
    )


def _fake_test_author(log_path):
    return (
        _log_prelude(log_path)
        + "GATE_VERSION = 'generated_test@3.0.0'\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log('author_test', {})\n"
        "    return {'component_id': 'comp-widget', 'criterion_id': 'AC-WIDGET-001',\n"
        "            'model': model, 'seed': seed, 'prompt_version': 'v1', 'cache_hit': False,\n"
        "            'file': {'path': 'verification/widget/generated-test/test_ac_widget_001.py',\n"
        "                     'content': 'def test_x():\\n    assert True\\n'},\n"
        "            'model_call_error': None, 'repair_attempts': 0, 'probe_findings': []}\n"
    )


def _fake_llm_endpoint(log_path):
    return (
        _log_prelude(log_path)
        + "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('complete', {})\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
        "def load_config(config_path=None):\n"
        "    return None\n"
    )


def _fake_provenance_checker(log_path):
    return (
        _log_prelude(log_path)
        + "import types\n"
        "GATE_VERSIONS = {\n"
        "    'compiler': 'criterion-compiler@1.0.0',\n"
        "    'generated_test': 'generated_test@3.0.0',\n"
        "    'verifier': 'verifier-orchestrator@3.5.0',\n"
        "    'license_scanner': 'license_scanner@4.0.3',\n"
        "    'secret_scanner': 'secret_scanner@0.0.0',\n"
        "    'generator': 'generator@3.2.0+v12',\n"
        "}\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', {'component_id': component_id})\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', {'component_id': component_id})\n"
        "    return types.SimpleNamespace(\n"
        "        spec_bundle_hash='sha256:abc123',\n"
        "        gate_versions=dict(GATE_VERSIONS),\n"
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                 'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
        "                 'lockfile_sha256': None}],\n"
        "    )\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', {'component_id': component_id})\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )


def _fake_assembler(log_path):
    return (
        _log_prelude(log_path)
        + "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    _log('assemble', {'component_id': component_id, 'mode': mode})\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:abc123',\n"
        "        'spec': 'widget doubles its input',\n"
        "        'interface': 'widget(x) -> int',\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': None,\n"
        "    }\n"
    )


def _fake_license_scanner(log_path):
    return (
        _log_prelude(log_path)
        + "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.3'\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', {'component_id': component_id})\n"
        "    return {'component_id': component_id, 'gate_version': 'license_scanner@4.0.3',\n"
        "            'similarity_score': 0.0, 'blocked': False, 'matches': [], 'evaluated': True}\n"
    )


def _fake_secret_scanner(log_path):
    return (
        _log_prelude(log_path)
        + "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan', {})\n"
        "    return {'scope': 'repo', 'gate_version': 'secret_scanner@0.0.0',\n"
        "            'flagged': False, 'matches': []}\n"
    )


def _fake_provenance_writer(log_path):
    return (
        _log_prelude(log_path)
        + "def _get(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name, None)\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', {'component_id': component_id})\n"
        "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
        "    gen = _get(inputs, 'generation_result')\n"
        "    manifest = {\n"
        "        'spec_bundle_hash': _get(gen, 'spec_bundle_hash'),\n"
        "        'model_pin': _get(gen, 'model'),\n"
        "        'prompt_version': _get(gen, 'prompt_version'),\n"
        "        'provenance_hit': _get(inputs, 'provenance_hit'),\n"
        "        'attempts': _get(inputs, 'attempts'),\n"
        "        'gate_versions': _get(inputs, 'gate_versions'),\n"
        "        'verification_report': _get(inputs, 'verification_report'),\n"
        "        'license_scan': _get(inputs, 'license_scan_result'),\n"
        "        'secret_scan': _get(inputs, 'secret_scan_result'),\n"
        "    }\n"
        "    text = json.dumps(manifest, default=str, sort_keys=True, indent=2) + '\\n'\n"
        "    for top in ('gen', 'verification'):\n"
        "        d = os.path.join(str(repo_root), top, slug)\n"
        "        os.makedirs(d, exist_ok=True)\n"
        "        with open(os.path.join(d, '.provenance.json'), 'w', encoding='utf-8') as f:\n"
        "            f.write(text)\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', {'component_id': component_id})\n"
    )


def _fake_provenance_tracker(log_path):
    return (
        _log_prelude(log_path)
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                          spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', {'component_id': component_id})\n"
        "    d = os.path.join(str(repo_root), '.hotdocs', 'attempts', component_id)\n"
        "    os.makedirs(d, exist_ok=True)\n"
        "    n = len(os.listdir(d)) + 1\n"
        "    with open(os.path.join(d, 'attempt-' + str(n) + '.json'), 'w', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'spec_bundle_hash': spec_bundle_hash}) + '\\n')\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {}\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _write_spec_corpus(repo):
    base = repo / "specs" / "components" / SLUG
    _write(
        base / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubles a number.\n",
    )
    _write(
        base / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n`widget(x)` MUST return `x * 2`.\n",
    )
    _write(
        base / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\nCovers: R-WIDGET-001\nKind: compiled\n\n"
        "```gherkin\nGiven a x is 2\nWhen widget is called with x\nThen result equals 4\n```\n",
    )
    _write(base / "interface" / "library.md", "# Library\n\n```\nwidget(x)\n```\n")
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_cs_zero_edit_001(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    log_path = tmp_path / "calls.log"

    _git(repo, ["init", "-q"], HUMAN_NAME, HUMAN_EMAIL)
    _git(repo, ["symbolic-ref", "HEAD", "refs/heads/main"], HUMAN_NAME, HUMAN_EMAIL)

    # Pipeline tooling stand-ins, committed before the spec change.
    fakes = {
        "generator/generator.py": _fake_generator(log_path),
        "surface-checker/surface_checker.py": _fake_surface_checker(log_path),
        "verifier-orchestrator/verifier_orchestrator.py": _fake_verifier(log_path),
        "test-author/test_author.py": _fake_test_author(log_path),
        "llm-endpoint/llm_endpoint.py": _fake_llm_endpoint(log_path),
        "provenance-checker/provenance_checker.py": _fake_provenance_checker(log_path),
        "spec-bundle-assembler/spec_bundle_assembler.py": _fake_assembler(log_path),
        "license-scanner/license_scanner.py": _fake_license_scanner(log_path),
        "secret-scanner/secret_scanner.py": _fake_secret_scanner(log_path),
        "provenance-writer/provenance_writer.py": _fake_provenance_writer(log_path),
        "provenance-tracker/provenance_tracker.py": _fake_provenance_tracker(log_path),
    }
    for rel, src in fakes.items():
        _write(repo / "gen" / rel, src)
    _write(repo / "README.md", "fixture\n")
    _git(repo, ["add", "-A"], HUMAN_NAME, HUMAN_EMAIL)
    _git(repo, ["commit", "-q", "-m", "tooling"], HUMAN_NAME, HUMAN_EMAIL)

    # The ratified spec change is merged by a human.
    _write_spec_corpus(repo)
    _git(repo, ["add", "-A"], HUMAN_NAME, HUMAN_EMAIL)
    _git(repo, ["commit", "-q", "-m", "spec: widget"], HUMAN_NAME, HUMAN_EMAIL)
    spec_merge = _git(repo, ["rev-parse", "HEAD"], HUMAN_NAME, HUMAN_EMAIL).strip()
    assert not (repo / "gen" / SLUG).exists()

    # The pipeline runs on its own branch.
    _git(repo, ["checkout", "-q", "-b", "pipeline/comp-widget"], PIPELINE_NAME, PIPELINE_EMAIL)
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo, MODEL, 0)

    # Every gate passes.
    assert field(result, "component_id") == COMPONENT_ID
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    assert field(field(result, "verification"), "overall") == "pass"
    assert field(field(result, "license_scan"), "blocked") is False
    assert field(field(result, "secret_scan"), "flagged") is False
    attempts = field(result, "attempts")
    assert len(attempts) >= 1
    assert field(attempts[-1], "outcome") == "passed"

    calls = [c["fn"] for c in _read_log(log_path)]
    assert "generate" in calls
    assert "verify" in calls
    assert "write_provenance" in calls

    widget_file = repo / "gen" / SLUG / "widget.py"
    assert widget_file.read_text(encoding="utf-8") == WIDGET_SRC
    assert (repo / "gen" / SLUG / ".provenance.json").is_file()

    # The pipeline commits and merges its own output.
    _git(repo, ["add", "-A"], PIPELINE_NAME, PIPELINE_EMAIL)
    _git(repo, ["commit", "-q", "-m", "pipeline: generate comp-widget"], PIPELINE_NAME, PIPELINE_EMAIL)
    _git(repo, ["checkout", "-q", "main"], PIPELINE_NAME, PIPELINE_EMAIL)
    _git(
        repo,
        ["merge", "-q", "--no-ff", "-m", "pipeline: merge comp-widget", "pipeline/comp-widget"],
        PIPELINE_NAME,
        PIPELINE_EMAIL,
    )
    pipeline_merge = _git(repo, ["rev-parse", "HEAD"], PIPELINE_NAME, PIPELINE_EMAIL).strip()
    merge_author = _git(
        repo, ["log", "-1", "--format=%an|%ae", pipeline_merge], PIPELINE_NAME, PIPELINE_EMAIL
    ).strip()
    assert merge_author == PIPELINE_NAME + "|" + PIPELINE_EMAIL

    # Zero human-authored commits to gen/<component>/ between the spec merge
    # and the pipeline's own merge commit.
    authors = _git(
        repo,
        ["log", "--format=%an|%ae", spec_merge + ".." + pipeline_merge, "--", "gen/" + SLUG],
        PIPELINE_NAME,
        PIPELINE_EMAIL,
    ).split()
    assert authors, "the pipeline itself must have committed gen/" + SLUG + "/"
    assert set(authors) == {PIPELINE_NAME + "|" + PIPELINE_EMAIL}

    # The merged gen/<component>/ is exactly what passed the gates, untouched.
    merged = _git(
        repo, ["show", pipeline_merge + ":gen/" + SLUG + "/widget.py"], PIPELINE_NAME, PIPELINE_EMAIL
    )
    assert merged == WIDGET_SRC
    status = _git(repo, ["status", "--porcelain", "--", "gen/" + SLUG], PIPELINE_NAME, PIPELINE_EMAIL)
    assert status.strip() == ""