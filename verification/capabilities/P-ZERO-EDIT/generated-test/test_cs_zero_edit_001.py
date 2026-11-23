# hotdocs-criterion: sha256:298f90934fdd4fc42f980b1731e3b6266c52f2d8a448adfeaac9b82d4e708b48
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
PIPELINE_EMAIL = "pipeline@hotdocs.invalid"

ADD_SOURCE = "def add(a, b):\n    return a + b\n"
SUB_SOURCE = "def subtract(a, b):\n    return a - b\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo, *args, name=HUMAN_NAME, email=HUMAN_EMAIL):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
    )
    completed = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args),
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _header(log):
    return (
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log)) + "\n"
        + r'''

def _log(fn, **data):
    entry = {'fn': fn}
    entry.update(data)
    with open(LOG, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, default=str) + '\n')


def _f(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _slug(component_id):
    if component_id.startswith('comp-'):
        return component_id[len('comp-'):]
    return component_id


def _spec_hash(repo_root, slug):
    import hashlib
    base = Path(repo_root) / 'specs' / 'components' / slug
    digest = hashlib.sha256()
    for path in sorted(p for p in base.rglob('*') if p.is_file()):
        digest.update(str(path.relative_to(base)).encode('utf-8'))
        digest.update(path.read_bytes())
    return 'sha256:' + digest.hexdigest()


'''
    )


PROVENANCE_CHECKER_BODY = r'''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions, assets):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions
        self.assets = assets


def current_sealed_key(component_id, repo_root):
    _log('current_sealed_key', component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log('current_provenance_key', component_id=component_id)
    return ProvenanceKey(
        _spec_hash(repo_root, _slug(component_id)),
        {
            'compiler': 'criterion-compiler@1.0.0',
            'generated_test': 'generated_test@3.0.0',
            'verifier': 'verifier-orchestrator@3.5.0',
            'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',
            'secret_scanner': 'secret_scanner@0.0.0',
            'generator': 'generator@3.2.0+v12',
        },
        [{'kind': 'python', 'path': '.', 'definition_sha256': None,
          'adapter_sha256': 'sha256:' + 'b' * 64,
          'versions': {'python': '3.12.0', 'packages': 'sha256:' + 'c' * 64},
          'lockfile_sha256': None}],
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log('check_provenance', component_id=component_id)
    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,
            'license_scan': None, 'secret_scan': None}


def check_sealed_provenance(component_id, repo_root):
    _log('check_sealed_provenance', component_id=component_id)
    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',
            'verification_report': None, 'license_scan': None, 'secret_scan': None,
            'owners': None, 'source_hash': None, 'written_at': None}
'''


ASSEMBLER_BODY = r'''
def _read_all(paths):
    parts = []
    for path in paths:
        text = path.read_text(encoding='utf-8').strip()
        if text:
            parts.append(text)
    return '\n\n'.join(parts)


def assemble(component_id, repo_root, mode='cold'):
    _log('assemble', component_id=component_id, mode=mode)
    slug = _slug(component_id)
    base = Path(repo_root) / 'specs' / 'components' / slug
    spec = _read_all([base / 'component.md'] + sorted((base / 'requirements').glob('*.md')))
    interface = _read_all(sorted((base / 'interface').rglob('*.md')))
    constraints_path = base / 'constraints.md'
    constraints = constraints_path.read_text(encoding='utf-8').strip() if constraints_path.is_file() else ''
    hint_code = None
    if mode == 'hint':
        hint_code = {}
        code_dir = Path(repo_root) / 'gen' / slug
        if code_dir.is_dir():
            for path in sorted(p for p in code_dir.rglob('*') if p.is_file()):
                hint_code[str(path.relative_to(code_dir))] = path.read_text(encoding='utf-8')
    return {
        'component_id': component_id,
        'spec_bundle_hash': _spec_hash(repo_root, slug),
        'spec': spec,
        'interface': interface,
        'constraints': constraints,
        'dependency_interfaces': {},
        'dependency_context': {},
        'dependency_usage': {},
        'vars': {},
        'glossary': '',
        'hint_code': hint_code,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)
    slug = _slug(component_id)
    base = Path(repo_root) / 'specs' / 'components' / slug
    text = (base / 'acceptance' / (criterion_id + '.md')).read_text(encoding='utf-8')
    covers = ''
    for line in text.splitlines():
        if line.startswith('Covers:'):
            covers = line[len('Covers:'):].strip()
    requirement = base / 'requirements' / (covers + '.md')
    return {
        'component_id': component_id,
        'criterion_id': criterion_id,
        'covers': covers,
        'criterion_text': text,
        'requirement_text': requirement.read_text(encoding='utf-8') if requirement.is_file() else '',
        'interface': _read_all(sorted((base / 'interface').rglob('*.md'))),
        'glossary': '',
        'dependency_interfaces': {},
        'testing': '',
    }
'''


GENERATOR_BODY = r'''
import dataclasses

GATE_VERSION = 'generator@3.2.0'
PROMPT_VERSION = 'v12'


@dataclasses.dataclass
class GenerationResult:
    component_id: str = ''
    spec_bundle_hash: str = ''
    model: str = ''
    prompt_version: str = ''
    cache_hit: bool = False
    files: dict = dataclasses.field(default_factory=dict)
    model_call_error: object = None
    refused: object = None
    retry_feedback: object = None
    mode: str = 'single'
    transcript_sha256: object = None
    turns: int = 1
    tool_calls: int = 0
    isolation: object = None


def _candidate(spec_text):
    source = ADD_SOURCE
    if 'subtract' in spec_text:
        source = ADD_SOURCE + '\n\n' + SUB_SOURCE
    return {'widget.py': source}


def check_write_allowed(bundle, repo_root=None):
    slug = _slug(_f(bundle, 'component_id'))
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    component_md = root / 'specs' / 'components' / slug / 'component.md'
    if component_md.is_file():
        for line in component_md.read_text(encoding='utf-8').splitlines():
            if line.strip() == 'sealed: true':
                return 'sealed-component'
    if (root / 'gen' / slug / '.overrides.json').is_file():
        return 'pinned-override'
    return None


def render_prompt_sections(bundle, retry_feedback=None):
    sections = [('Spec', _f(bundle, 'spec') or ''), ('Component interface', _f(bundle, 'interface') or '')]
    if retry_feedback:
        sections.append(('Retry feedback', ', '.join(retry_feedback)))
    return sections


def write_files(component_id, files, repo_root=None):
    _log('write_files', component_id=component_id, paths=sorted(files))
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    code_dir = root / 'gen' / _slug(component_id)
    for relative, content in files.items():
        target = code_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')


def check_assets(component_id, files, repo_root=None):
    _log('check_assets', component_id=component_id)
    return (None, [])


def check_asset_environment(component_id, repo_root=None):
    _log('check_asset_environment', component_id=component_id)
    return (None, [])


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = _f(bundle, 'component_id')
    _log('generate', component_id=component_id, model=model, retry_feedback=retry_feedback)
    common = dict(component_id=component_id, spec_bundle_hash=_f(bundle, 'spec_bundle_hash'),
                  model=model, prompt_version=PROMPT_VERSION, retry_feedback=retry_feedback)
    refusal = check_write_allowed(bundle, repo_root=repo_root)
    if refusal is not None:
        return GenerationResult(refused=refusal, **common)
    files = _candidate(_f(bundle, 'spec') or '')
    if _f(bundle, 'hint_code') is None:
        write_files(component_id, files, repo_root=repo_root)
    return GenerationResult(files=dict(files), **common)


def commit_cache(result, repo_root=None):
    _log('commit_cache', component_id=_f(result, 'component_id'))
'''


SURFACE_BODY = r'''
GATE_VERSION = 'surface-checker@1.2.0'


def check_surface(component_id, repo_root, code_dir=None):
    _log('check_surface', component_id=component_id)
    slug = _slug(component_id)
    module = slug.replace('-', '_')
    base = Path(code_dir) if code_dir is not None else Path(repo_root) / 'gen' / slug
    if (base / (module + '.py')).is_file() or (base / module / '__init__.py').is_file():
        return {'ok': True, 'findings': []}
    return {'ok': False, 'findings': [{'kind': 'import_error', 'message': 'No module named ' + module}]}
'''


VERIFIER_BODY = r'''
import importlib.util

GATE_VERSION = 'verifier-orchestrator@3.5.0'
DEFAULT_TEST_TIMEOUT = 300.0

CHECKS = {
    'AC-WIDGET-001': ('add', (2, 3), 5),
    'AC-WIDGET-002': ('subtract', (5, 3), 2),
}


def _load_candidate(path, module_name):
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous
        sys.modules.pop(module_name, None)


def verify(component_id, repo_root, judge=None, test_author=None):
    slug = _slug(component_id)
    module_name = slug.replace('-', '_')
    acceptance = Path(repo_root) / 'specs' / 'components' / slug / 'acceptance'
    candidate_path = Path(repo_root) / 'gen' / slug / (module_name + '.py')
    candidate = None
    try:
        candidate = _load_candidate(candidate_path, 'hotdocs_fake_verify_' + module_name)
    except Exception:
        candidate = None
    criteria = []
    requirement_results = {}
    for path in sorted(acceptance.glob('*.md')):
        criterion_id = path.stem
        covers = ''
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('Covers:'):
                covers = line[len('Covers:'):].strip()
        check = CHECKS.get(criterion_id)
        passed = False
        actual = None
        if candidate is not None and check is not None:
            name, args, expected = check
            fn = getattr(candidate, name, None)
            if callable(fn):
                try:
                    actual = fn(*args)
                except Exception as exc:
                    actual = repr(exc)
                passed = actual == expected
        entry = {'id': criterion_id, 'covers': covers, 'kind': 'generated-test',
                 'result': 'pass' if passed else 'fail'}
        if not passed:
            entry['failure_detail'] = {'message': criterion_id + ' failed',
                                       'expected': check[2] if check else None, 'actual': actual}
            entry['failure_origin'] = 'implementation'
        criteria.append(entry)
        if covers:
            if requirement_results.get(covers) == 'fail':
                continue
            requirement_results[covers] = entry['result']
    overall = 'pass' if criteria and all(c['result'] == 'pass' for c in criteria) else 'fail'
    _log('verify', component_id=component_id, overall=overall,
         criteria=[c['id'] + ':' + c['result'] for c in criteria])
    return {
        'component_id': component_id,
        'criteria': criteria,
        'requirement_results': requirement_results,
        'interface_drift': False,
        'mutation_score': 1.0,
        'mutation_error': None,
        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,
                    'adapter_sha256': 'sha256:' + 'b' * 64,
                    'versions': {'python': '3.12.0'}, 'lockfile_sha256': None}],
        'overall': overall,
    }
'''


TRACKER_BODY = r'''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    overall = _f(verification_report, 'overall') if verification_report is not None else None
    _log('write_attempt_record', component_id=component_id, overall=overall)
'''


LICENSE_BODY = r'''
GATE = 'license_scanner@4.0.3+9f2c41ab07de'


def gate_version(repo_root):
    return GATE


def scan(component_id, repo_root):
    _log('license_scan', component_id=component_id)
    return {'component_id': component_id, 'gate_version': GATE, 'similarity_score': 0.0,
            'blocked': False, 'matches': [], 'evaluated': True}
'''


SECRET_BODY = r'''
GATE = 'secret_scanner@0.0.0'


def gate_version(repo_root):
    return GATE


def scan(repo_root):
    _log('secret_scan')
    return {'scope': str(repo_root), 'gate_version': GATE, 'flagged': False, 'matches': []}
'''


WRITER_BODY = r'''
class MissingInputError(Exception):
    pass


class InvalidSealedInputError(ValueError):
    pass


def write_provenance(component_id, inputs, repo_root):
    generation_result = _f(inputs, 'generation_result')
    verification_report = _f(inputs, 'verification_report')
    files = _f(generation_result, 'files') or {}
    if files and verification_report is None:
        raise MissingInputError('verification_report')
    slug = _slug(component_id)
    manifest = {
        'component_id': component_id,
        'spec_bundle_hash': _f(generation_result, 'spec_bundle_hash'),
        'model_pin': _f(generation_result, 'model'),
        'prompt_version': _f(generation_result, 'prompt_version'),
        'attempts': _f(inputs, 'attempts'),
        'gate_versions': _f(inputs, 'gate_versions'),
        'provenance_hit': False,
        'verification_overall': _f(verification_report, 'overall'),
    }
    for directory in (Path(repo_root) / 'gen' / slug, Path(repo_root) / 'verification' / slug):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / '.provenance.json').write_text(
            json.dumps(manifest, indent=2, sort_keys=True, default=str) + '\n', encoding='utf-8')
    _log('write_provenance', component_id=component_id)


def write_sealed_provenance(component_id, inputs, repo_root):
    _log('write_sealed_provenance', component_id=component_id)
'''


def _write_fakes(repo, log):
    header = _header(log)
    gen = repo / "gen"
    _write(gen / "provenance-checker" / "provenance_checker.py", header + PROVENANCE_CHECKER_BODY)
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", header + ASSEMBLER_BODY)
    _write(
        gen / "generator" / "generator.py",
        header
        + "ADD_SOURCE = " + repr(ADD_SOURCE) + "\n"
        + "SUB_SOURCE = " + repr(SUB_SOURCE) + "\n"
        + GENERATOR_BODY,
    )
    _write(gen / "surface-checker" / "surface_checker.py", header + SURFACE_BODY)
    _write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", header + VERIFIER_BODY)
    _write(gen / "provenance-tracker" / "provenance_tracker.py", header + TRACKER_BODY)
    _write(gen / "license-scanner" / "license_scanner.py", header + LICENSE_BODY)
    _write(gen / "secret-scanner" / "secret_scanner.py", header + SECRET_BODY)
    _write(gen / "provenance-writer" / "provenance_writer.py", header + WRITER_BODY)


def _component_md():
    return (
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: ratified\n"
        "owners: [widget-team]\n"
        "last_ratified_commit: 0000000\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Small arithmetic helpers.\n"
    )


def _acceptance(criterion_id, covers, when, then):
    return (
        "# " + criterion_id + "\n"
        "\n"
        "Covers: " + covers + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the widget module\n"
        "When " + when + "\n"
        "Then " + then + "\n"
        "```\n"
    )


def _write_spec_v1(repo):
    base = repo / "specs" / "components" / "widget"
    _write(base / "component.md", _component_md())
    _write(base / "constraints.md", "# Constraints\n\nStandard library only.\n")
    _write(base / "interface" / "library.md", "# Library\n\n```\nadd(a, b)\n```\n")
    _write(
        base / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\nThe module MUST provide add(a, b) returning a + b.\n",
    )
    _write(
        base / "acceptance" / "AC-WIDGET-001.md",
        _acceptance("AC-WIDGET-001", "R-WIDGET-001", "add is called with 2 and 3", "the result is 5"),
    )


def _write_spec_change(repo):
    base = repo / "specs" / "components" / "widget"
    _write(base / "interface" / "library.md", "# Library\n\n```\nadd(a, b)\nsubtract(a, b)\n```\n")
    _write(
        base / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\nThe module MUST provide subtract(a, b) returning a - b.\n",
    )
    _write(
        base / "acceptance" / "AC-WIDGET-002.md",
        _acceptance("AC-WIDGET-002", "R-WIDGET-002", "subtract is called with 5 and 3", "the result is 2"),
    )


def _read_log(log):
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_cs_zero_edit_001_spec_change_merges_with_zero_human_edits_to_gen(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to model the spec merge and the pipeline merge commit")

    repo = tmp_path / "repo"
    repo.mkdir()
    log = tmp_path / "calls.log"

    _git(repo, "init", "-q")
    _write(repo / ".gitignore", "__pycache__/\n.hotdocs/\n")
    _write_fakes(repo, log)
    _write_spec_v1(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Initial corpus")

    # The ratified spec change is merged by a human.
    _write_spec_change(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Merge spec change: R-WIDGET-002")
    spec_sha = _git(repo, "rev-parse", "HEAD").strip()

    assert _git(repo, "ls-tree", "-r", "--name-only", spec_sha, "--", "gen/widget").strip() == ""
    assert not (repo / "gen" / "widget").exists()

    # The pipeline runs, untouched by any human.
    result = component_gate_runner.run_component_gates("comp-widget", repo, "mock-model", 0)

    assert field(result, "component_id") == "comp-widget"
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None

    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
    criteria = field(verification, "criteria")
    assert sorted(field(c, "id") for c in criteria) == ["AC-WIDGET-001", "AC-WIDGET-002"]
    assert all(field(c, "result") == "pass" for c in criteria)

    license_scan = field(result, "license_scan")
    secret_scan = field(result, "secret_scan")
    assert field(license_scan, "blocked") is False
    assert field(secret_scan, "flagged") is False

    attempts = field(result, "attempts")
    assert len(attempts) >= 1
    assert field(attempts[-1], "outcome") == "passed"

    calls = _read_log(log)
    fns = [c["fn"] for c in calls]
    assert "generate" in fns
    assert "verify" in fns
    assert "license_scan" in fns
    assert "secret_scan" in fns
    assert fns.count("write_provenance") == 1

    generated = repo / "gen" / "widget" / "widget.py"
    assert generated.is_file()
    verified_content = generated.read_text(encoding="utf-8")

    # The pipeline's own merge commit, the only thing touching gen/widget/.
    _git(repo, "add", "--", "gen/widget")
    _git(repo, "commit", "-q", "-m", "hotdocs: regenerate comp-widget", name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    pipeline_sha = _git(repo, "rev-parse", "HEAD").strip()
    assert pipeline_sha != spec_sha

    gen_commits = [
        line.split("\t")
        for line in _git(
            repo, "log", "--format=%H\t%an\t%ae\t%cn\t%ce", spec_sha + ".." + pipeline_sha, "--", "gen/widget"
        ).splitlines()
        if line.strip()
    ]
    assert len(gen_commits) == 1
    sha, author_name, author_email, committer_name, committer_email = gen_commits[0]
    assert sha == pipeline_sha
    assert (author_name, author_email) == (PIPELINE_NAME, PIPELINE_EMAIL)
    assert (committer_name, committer_email) == (PIPELINE_NAME, PIPELINE_EMAIL)

    human_commits = [
        line
        for line in _git(repo, "log", "--format=%H\t%ae", spec_sha + ".." + pipeline_sha, "--", "gen/widget").splitlines()
        if line.strip() and line.split("\t")[1] != PIPELINE_EMAIL
    ]
    assert human_commits == []

    changed = set(
        line
        for line in _git(repo, "diff", "--name-only", spec_sha, pipeline_sha, "--", "gen/widget").splitlines()
        if line.strip()
    )
    assert changed == {"gen/widget/widget.py", "gen/widget/.provenance.json"}

    # What was merged is exactly what passed every gate.
    assert _git(repo, "show", pipeline_sha + ":gen/widget/widget.py") == verified_content
    assert _git(repo, "status", "--porcelain", "--", "gen/widget").strip() == ""