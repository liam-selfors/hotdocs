# hotdocs-criterion: sha256:e677455fb0229920045a7bce371f77d8afd2c520fda31c704e803236f51a825f
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


HUMAN_NAME = "Spec Author"
HUMAN_EMAIL = "spec-author@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@example.invalid"

COMPONENT_ID = "comp-widget"
SLUG = "widget"
SPEC_HASH = "sha256:" + "ab" * 32
GENERATED_SOURCE = "def widen(x):\n    return x * 2\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args, author=None):
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    name, email = author if author else (HUMAN_NAME, HUMAN_EMAIL)
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), env=env, check=True,
        capture_output=True, text=True,
    )
    return proc.stdout


COMMON = (
    "import json\n"
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(call, **kw):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps({'module': MOD, 'call': call, 'args': kw}, default=str) + '\\n')\n"
    "\n"
)

PROVENANCE_CHECKER_BODY = (
    "class _Key:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id)\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id)\n"
    "    return _Key(SPEC_HASH, {\n"
    "        'compiler': 'criterion-compiler@1.0.0',\n"
    "        'generated_test': 'generated_test@3.0.0',\n"
    "        'verifier': 'verifier-orchestrator@3.5.0',\n"
    "        'license_scanner': 'license_scanner@4.0.3',\n"
    "        'secret_scanner': 'secret_scanner@0.0.0',\n"
    "        'generator': 'generator@3.2.0+v12',\n"
    "    }, [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "         'adapter_sha256': 'sha256:00', 'versions': {}, 'lockfile_sha256': None}])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

ASSEMBLER_BODY = (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, mode=mode)\n"
    "    slug = component_id[len('comp-'):]\n"
    "    spec = (Path(repo_root) / 'specs' / 'components' / slug / 'requirements' / 'R-WIDGET-001.md').read_text()\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': SPEC_HASH,\n"
    "            'spec': spec, 'interface': 'widen(x)', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-WIDGET-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': 'widen(x)', 'glossary': '', 'dependency_interfaces': {},\n"
    "            'testing': ''}\n"
)

GENERATOR_BODY = (
    "GATE_VERSION = 'generator@3.2.0'\n"
    "PROMPT_VERSION = 'v12'\n"
    "\n"
    "def _result(bundle, model, retry_feedback, files):\n"
    "    return {'component_id': bundle['component_id'],\n"
    "            'spec_bundle_hash': bundle['spec_bundle_hash'], 'model': model,\n"
    "            'prompt_version': PROMPT_VERSION, 'cache_hit': False, 'files': files,\n"
    "            'model_call_error': None, 'refused': None,\n"
    "            'retry_feedback': retry_feedback, 'mode': 'single',\n"
    "            'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
    "\n"
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    _log('generate', component_id=bundle['component_id'], model=model,\n"
    "         retry_feedback=retry_feedback, hint_code=bundle['hint_code'])\n"
    "    files = {'widget.py': GENERATED_SOURCE}\n"
    "    if bundle['hint_code'] is None:\n"
    "        write_files(bundle['component_id'], files, repo_root=repo_root)\n"
    "    return _result(bundle, model, retry_feedback, files)\n"
    "\n"
    "def commit_cache(result, repo_root=None):\n"
    "    _log('commit_cache')\n"
    "\n"
    "def check_write_allowed(bundle, repo_root=None):\n"
    "    return None\n"
    "\n"
    "def render_prompt_sections(bundle, retry_feedback=None):\n"
    "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
    "\n"
    "def write_files(component_id, files, repo_root=None):\n"
    "    slug = component_id[len('comp-'):]\n"
    "    out = Path(repo_root) / 'gen' / slug\n"
    "    out.mkdir(parents=True, exist_ok=True)\n"
    "    for rel, content in files.items():\n"
    "        (out / rel).write_text(content)\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    return (None, [])\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    return (None, [])\n"
)

SURFACE_BODY = (
    "GATE_VERSION = 'surface-checker@1.2.0'\n"
    "\n"
    "def check_surface(component_id, repo_root, code_dir=None):\n"
    "    _log('check_surface', component_id=component_id)\n"
    "    return {'ok': True, 'findings': []}\n"
)

VERIFIER_BODY = (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    slug = component_id[len('comp-'):]\n"
    "    path = Path(repo_root) / 'gen' / slug / 'widget.py'\n"
    "    ok = path.is_file() and path.read_text() == GENERATED_SOURCE\n"
    "    _log('verify', component_id=component_id, ok=ok)\n"
    "    result = 'pass' if ok else 'fail'\n"
    "    crit = {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001',\n"
    "            'kind': 'generated-test', 'result': result}\n"
    "    if not ok:\n"
    "        crit['failure_detail'] = {'message': 'widen missing', 'expected': None, 'actual': None}\n"
    "        crit['failure_origin'] = 'implementation'\n"
    "    return {'component_id': component_id, 'criteria': [crit],\n"
    "            'requirement_results': {'R-WIDGET-001': result},\n"
    "            'interface_drift': False, 'mutation_score': 1.0 if ok else None,\n"
    "            'mutation_error': None,\n"
    "            'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:00', 'versions': {},\n"
    "                        'lockfile_sha256': None}],\n"
    "            'overall': result}\n"
)

LICENSE_BODY = (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.3'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id)\n"
    "    return {'component_id': component_id, 'gate_version': 'license_scanner@4.0.3',\n"
    "            'similarity_score': 0.0, 'blocked': False, 'matches': [],\n"
    "            'evaluated': True}\n"
)

SECRET_BODY = (
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return {'scope': 'repo', 'gate_version': 'secret_scanner@0.0.0',\n"
    "            'flagged': False, 'matches': []}\n"
)

WRITER_BODY = (
    "def _get(v, n):\n"
    "    return v[n] if isinstance(v, dict) else getattr(v, n)\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id)\n"
    "    slug = component_id[len('comp-'):]\n"
    "    gen_result = _get(inputs, 'generation_result')\n"
    "    report = _get(inputs, 'verification_report')\n"
    "    doc = {'spec_bundle_hash': _get(gen_result, 'spec_bundle_hash'),\n"
    "           'model_pin': _get(gen_result, 'model'),\n"
    "           'prompt_version': _get(gen_result, 'prompt_version'),\n"
    "           'provenance_hit': False,\n"
    "           'verification_report': report if isinstance(report, dict) else report.to_dict(),\n"
    "           'gate_versions': _get(inputs, 'gate_versions')}\n"
    "    for base in ('gen', 'verification'):\n"
    "        d = Path(repo_root) / base / slug\n"
    "        d.mkdir(parents=True, exist_ok=True)\n"
    "        (d / '.provenance.json').write_text(json.dumps(doc, sort_keys=True, default=str) + '\\n')\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id)\n"
)

TRACKER_BODY = (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id)\n"
)

FAKES = [
    ("provenance-checker", "provenance_checker", PROVENANCE_CHECKER_BODY),
    ("spec-bundle-assembler", "spec_bundle_assembler", ASSEMBLER_BODY),
    ("generator", "generator", GENERATOR_BODY),
    ("surface-checker", "surface_checker", SURFACE_BODY),
    ("verifier-orchestrator", "verifier_orchestrator", VERIFIER_BODY),
    ("license-scanner", "license_scanner", LICENSE_BODY),
    ("secret-scanner", "secret_scanner", SECRET_BODY),
    ("provenance-writer", "provenance_writer", WRITER_BODY),
    ("provenance-tracker", "provenance_tracker", TRACKER_BODY),
]


def write_fakes(repo_root, log_path):
    for slug, module, body in FAKES:
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        source = (
            "LOG = " + repr(str(log_path)) + "\n"
            + "MOD = " + repr(module) + "\n"
            + "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
            + "GENERATED_SOURCE = " + repr(GENERATED_SOURCE) + "\n"
            + COMMON
            + body
        )
        (d / (module + ".py")).write_text(source)


def write_spec(repo_root, requirement_text):
    comp = repo_root / "specs" / "components" / SLUG
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n\n# Widget\n\n## Purpose\n\nDoubles numbers.\n"
    )
    (comp / "requirements" / "R-WIDGET-001.md").write_text(
        "# R-WIDGET-001\n\n" + requirement_text + "\n"
    )
    (comp / "acceptance" / "AC-WIDGET-001.md").write_text(
        "# AC-WIDGET-001\n\nCovers: R-WIDGET-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x is 2\nWhen widen is called\nThen the result is 4\n```\n"
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nwiden(x: int) -> int\n```\n"
    )


def test_cs_zero_edit_001(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "calls.log"

    git(repo_root, "init", "-q")
    (repo_root / ".gitignore").write_text("__pycache__/\n")
    write_fakes(repo_root, log_path)
    write_spec(repo_root, "`widen` MUST return its argument multiplied by one.")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "baseline")

    # The ratified spec change is merged by a human.
    write_spec(repo_root, "`widen` MUST return its argument multiplied by two.")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "Spec merge: widen doubles")
    spec_merge = git(repo_root, "rev-parse", "HEAD").strip()

    # The pipeline runs, with no human touching gen/widget/.
    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "claude-sonnet-5", 0
    )

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

    gen_dir = repo_root / "gen" / SLUG
    assert (gen_dir / "widget.py").read_text() == GENERATED_SOURCE
    assert (gen_dir / ".provenance.json").is_file()

    calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    names = [c["call"] for c in calls]
    assert "generate" in names
    assert "verify" in names
    assert "write_provenance" in names
    assert all(c["args"].get("ok") for c in calls if c["call"] == "verify")

    # The pipeline's own merge commit.
    git(repo_root, "add", "-A", "--", "gen/" + SLUG, "verification")
    git(
        repo_root, "commit", "-q", "-m", "Pipeline merge: regenerate comp-widget",
        author=(PIPELINE_NAME, PIPELINE_EMAIL),
    )
    pipeline_merge = git(repo_root, "rev-parse", "HEAD").strip()
    assert pipeline_merge != spec_merge

    # Nothing left uncommitted under gen/widget/ for a human to fix.
    assert git(repo_root, "status", "--porcelain", "--", "gen/" + SLUG).strip() == ""

    authors = [
        line for line in git(
            repo_root, "log", "--format=%an <%ae>",
            spec_merge + ".." + pipeline_merge, "--", "gen/" + SLUG,
        ).splitlines() if line.strip()
    ]
    assert len(authors) >= 1
    human_commits = [a for a in authors if a != PIPELINE_NAME + " <" + PIPELINE_EMAIL + ">"]
    assert human_commits == []