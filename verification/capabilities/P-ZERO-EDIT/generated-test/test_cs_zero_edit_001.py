# hotdocs-criterion: sha256:af544163d427747bb766b501c90d2ee5ac211d838024ab37e17679cde72ea8bb
import importlib.util
import json
import os
import shutil
import subprocess
import sys
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


HUMAN_NAME = "Dana Developer"
HUMAN_EMAIL = "dana.developer@example.com"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@hotdocs.invalid"

COMPONENT_ID = "comp-widget"
SLUG = "widget"
SPEC_HASH = "sha256:" + "ab" * 32


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args, author=None):
    env = dict(os.environ)
    name, email = author if author else (HUMAN_NAME, HUMAN_EMAIL)
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "user.name=" + name,
         "-c", "user.email=" + email, *args],
        cwd=str(repo), env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, (args, proc.stdout, proc.stderr)
    return proc.stdout


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def log_header(log_path):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps(entry, default=str) + '\\n')\n"
        "\n"
        "\n"
    )


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def build_fakes(repo, logs):
    gen = repo / "gen"

    write(gen / "provenance-checker" / "provenance_checker.py", log_header(logs / "provenance_checker.log") + (
        "import types\n"
        "\n"
        "GATE_VERSIONS = {\n"
        "    'compiler': 'criterion-compiler@1.0.0',\n"
        "    'generated_test': 'generated_test@3.0.0',\n"
        "    'verifier': 'verifier-orchestrator@3.5.0',\n"
        "    'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "    'secret_scanner': 'secret_scanner@0.0.0',\n"
        "    'generator': 'generator@3.2.0+v12',\n"
        "}\n"
        "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
        "    return None\n"
        "\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
        "    return types.SimpleNamespace(\n"
        "        spec_bundle_hash=" + repr(SPEC_HASH) + ",\n"
        "        gate_versions=dict(GATE_VERSIONS),\n"
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                 'adapter_sha256': 'sha256:' + '00' * 32,\n"
        "                 'versions': {'python': '3.14.6', 'packages': 'sha256:' + '11' * 32},\n"
        "                 'lockfile_sha256': None}],\n"
        "    )\n"
        "\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log({'call': 'check_provenance', 'component_id': component_id})\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", log_header(logs / "assembler.log") + (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log({'call': 'assemble', 'component_id': component_id, 'mode': mode})\n"
        "    root = Path(repo_root) / 'specs' / 'components' / 'widget'\n"
        "    spec = (root / 'component.md').read_text() + '\\n' + (root / 'requirements' / 'R-WIDGET-001.md').read_text()\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': " + repr(SPEC_HASH) + ",\n"
        "        'spec': spec,\n"
        "        'interface': (root / 'interface' / 'library.md').read_text(),\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': None,\n"
        "    }\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    raise RuntimeError('not used')\n"
    ))

    write(gen / "generator" / "generator.py", log_header(logs / "generator.log") + (
        "GATE_VERSION = 'generator@3.2.0'\n"
        "PROMPT_VERSION = 'v12'\n"
        "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log({'call': 'generate', 'component_id': bundle['component_id'], 'model': model,\n"
        "          'retry_feedback': retry_feedback})\n"
        "    files = {'widget.py': 'def widget(x):\\n    return x + 1\\n'}\n"
        "    out = Path(repo_root) / 'gen' / 'widget'\n"
        "    out.mkdir(parents=True, exist_ok=True)\n"
        "    for name, content in files.items():\n"
        "        (out / name).write_text(content)\n"
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
        "\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log({'call': 'commit_cache'})\n"
        "    return None\n"
    ))

    write(gen / "surface-checker" / "surface_checker.py", log_header(logs / "surface.log") + (
        "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log({'call': 'check_surface', 'component_id': component_id})\n"
        "    return {'ok': True, 'findings': []}\n"
    ))

    write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", log_header(logs / "verifier.log") + (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    code = (Path(repo_root) / 'gen' / 'widget' / 'widget.py').read_text()\n"
        "    ns = {}\n"
        "    exec(compile(code, 'widget.py', 'exec'), ns)\n"
        "    ok = ns['widget'](1) == 2\n"
        "    result = 'pass' if ok else 'fail'\n"
        "    _log({'call': 'verify', 'component_id': component_id, 'result': result})\n"
        "    criterion = {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001', 'kind': 'compiled',\n"
        "                 'result': result}\n"
        "    if not ok:\n"
        "        criterion['failure_detail'] = {'message': 'widget(1) equals 2 failed', 'expected': 2,\n"
        "                                       'actual': ns['widget'](1)}\n"
        "        criterion['failure_origin'] = 'implementation'\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [criterion],\n"
        "        'requirement_results': {'R-WIDGET-001': result},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 1.0,\n"
        "        'mutation_error': None,\n"
        "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                    'adapter_sha256': 'sha256:' + '00' * 32,\n"
        "                    'versions': {'python': '3.14.6'}, 'lockfile_sha256': None}],\n"
        "        'overall': result,\n"
        "    }\n"
    ))

    write(gen / "license-scanner" / "license_scanner.py", log_header(logs / "license.log") + (
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.3+9f2c41ab07de'\n"
        "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log({'call': 'license_scan', 'component_id': component_id})\n"
        "    return {'component_id': component_id, 'gate_version': gate_version(repo_root),\n"
        "            'similarity_score': 0.0, 'blocked': False, 'matches': [], 'evaluated': True}\n"
    ))

    write(gen / "secret-scanner" / "secret_scanner.py", log_header(logs / "secret.log") + (
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
        "\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log({'call': 'secret_scan'})\n"
        "    return {'scope': 'repo', 'gate_version': gate_version(repo_root),\n"
        "            'flagged': False, 'matches': []}\n"
    ))

    write(gen / "provenance-writer" / "provenance_writer.py", log_header(logs / "writer.log") + (
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log({'call': 'write_provenance', 'component_id': component_id})\n"
        "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
        "    text = json.dumps({'component_id': component_id, 'provenance_hit': False}, indent=2)\n"
        "    for base in ('gen', 'verification'):\n"
        "        target = Path(repo_root) / base / slug / '.provenance.json'\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(text + '\\n')\n"
        "\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log({'call': 'write_sealed_provenance', 'component_id': component_id})\n"
    ))

    write(gen / "provenance-tracker" / "provenance_tracker.py", log_header(logs / "tracker.log") + (
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log({'call': 'write_attempt_record', 'component_id': component_id})\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    ))

    write(gen / "test-author" / "test_author.py", log_header(logs / "test_author.log") + (
        "GATE_VERSION = 'generated_test@3.0.0'\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log({'call': 'author_test'})\n"
        "    return {'component_id': 'comp-widget', 'criterion_id': 'AC-WIDGET-001', 'model': model,\n"
        "            'seed': seed, 'prompt_version': 'v1', 'cache_hit': False,\n"
        "            'file': {'path': 'verification/widget/generated-test/test_ac_widget_001.py',\n"
        "                     'content': 'def test_x():\\n    pass\\n'},\n"
        "            'model_call_error': None, 'repair_attempts': 0, 'probe_findings': []}\n"
    ))

    write(gen / "llm-endpoint" / "llm_endpoint.py", log_header(logs / "llm.log") + (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log({'call': 'complete'})\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
        "\n"
        "\n"
        "def load_config(config_path=None):\n"
        "    return None\n"
    ))


def build_specs(repo, requirement_text):
    root = repo / "specs" / "components" / SLUG
    write(root / "component.md", (
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
        "Increments a number.\n"
    ))
    write(root / "requirements" / "R-WIDGET-001.md", requirement_text)
    write(root / "acceptance" / "AC-WIDGET-001.md", (
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a value is 1\n"
        "When widget is called with value\n"
        "Then the result equals 2\n"
        "```\n"
    ))
    write(root / "interface" / "library.md", (
        "# Library\n"
        "\n"
        "```\n"
        "widget(x: int) -> int\n"
        "```\n"
    ))


def test_cs_zero_edit_001_pipeline_merge_has_no_human_commits_to_gen(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required for this scenario")

    repo = tmp_path / "repo"
    repo.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()

    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")

    write(repo / ".gitignore", "__pycache__/\n.hotdocs/\n")
    build_fakes(repo, logs)
    build_specs(repo, (
        "# R-WIDGET-001\n"
        "\n"
        "`widget(x)` MUST return a number.\n"
    ))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Initial corpus")

    # A human authors and merges a spec change.
    git(repo, "checkout", "-q", "-b", "spec-change")
    build_specs(repo, (
        "# R-WIDGET-001\n"
        "\n"
        "`widget(x)` MUST return `x + 1`.\n"
    ))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Spec: widget increments")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "spec-change", "-m", "Merge spec change")
    spec_merge = git(repo, "rev-parse", "HEAD").strip()

    assert not (repo / "gen" / SLUG).exists()

    # The pipeline runs: generation -> verification -> scans -> provenance.
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo, "mock-model", 0)

    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    assert field(result, "provenance_hit") is False
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
    for criterion in field(verification, "criteria"):
        assert field(criterion, "result") == "pass"
    license_scan = field(result, "license_scan")
    assert field(license_scan, "blocked") is not True
    secret_scan = field(result, "secret_scan")
    assert field(secret_scan, "flagged") is not True
    attempts = field(result, "attempts")
    assert len(attempts) >= 1
    assert field(attempts[-1], "outcome") == "passed"

    # Every gate actually ran.
    assert any(e["call"] == "generate" for e in read_log(logs / "generator.log"))
    assert any(e["call"] == "check_surface" for e in read_log(logs / "surface.log"))
    assert any(e["call"] == "verify" and e["result"] == "pass" for e in read_log(logs / "verifier.log"))
    assert any(e["call"] == "license_scan" for e in read_log(logs / "license.log"))
    assert any(e["call"] == "secret_scan" for e in read_log(logs / "secret.log"))
    assert any(e["call"] == "write_provenance" for e in read_log(logs / "writer.log"))

    assert (repo / "gen" / SLUG / "widget.py").is_file()

    # The pipeline commits and merges its own output.
    git(repo, "checkout", "-q", "-b", "pipeline/regen-widget", author=(PIPELINE_NAME, PIPELINE_EMAIL))
    git(repo, "add", "-A", "gen/" + SLUG, "verification/" + SLUG, author=(PIPELINE_NAME, PIPELINE_EMAIL))
    git(repo, "commit", "-q", "-m", "Regenerate comp-widget", author=(PIPELINE_NAME, PIPELINE_EMAIL))
    git(repo, "checkout", "-q", "main", author=(PIPELINE_NAME, PIPELINE_EMAIL))
    git(repo, "merge", "-q", "--no-ff", "pipeline/regen-widget", "-m", "Pipeline merge comp-widget",
        author=(PIPELINE_NAME, PIPELINE_EMAIL))
    pipeline_merge = git(repo, "rev-parse", "HEAD").strip()

    log = git(repo, "log", "--full-history", "--format=%H%x09%an%x09%ae",
              spec_merge + ".." + pipeline_merge, "--", "gen/" + SLUG + "/")
    entries = [line.split("\t") for line in log.splitlines() if line.strip()]
    assert entries, "the pipeline's own commits must be what touched gen/widget/"
    human_commits = [e for e in entries if e[2] != PIPELINE_EMAIL]
    assert human_commits == []

    # The merged tree is clean and still carries the generated code.
    assert git(repo, "status", "--porcelain", "gen/" + SLUG).strip() == ""
    merged = git(repo, "show", pipeline_merge + ":gen/" + SLUG + "/widget.py")
    assert "return x + 1" in merged