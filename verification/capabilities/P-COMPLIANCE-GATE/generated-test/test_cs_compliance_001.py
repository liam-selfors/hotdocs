# hotdocs-criterion: sha256:5ac2f4a22e98c40855255225c68e0402fb0d0f7b17c55173f89a14870d55ce22
"""CS-COMPLIANCE-001: licensed-code similarity above threshold blocks the merge,
is recorded in the provenance manifest's license_scan field whatever the outcome,
and surfaces in the review packet even after a generation retry resolved the
attempt-level failure."""

import contextlib
import hashlib
import io
import json
import re
from pathlib import Path

import component_gate_runner
import license_scanner
import provenance_writer
import review_packet_builder
import secret_scanner


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODEL = "anthropic:claude-sonnet-5"

LICENSED_CODE = (
    "def merge_sorted_runs(left_run, right_run, comparator):\n"
    "    merged_output = []\n"
    "    left_index = 0\n"
    "    right_index = 0\n"
    "    while left_index < len(left_run) and right_index < len(right_run):\n"
    "        if comparator(left_run[left_index], right_run[right_index]) <= 0:\n"
    "            merged_output.append(left_run[left_index])\n"
    "            left_index = left_index + 1\n"
    "        else:\n"
    "            merged_output.append(right_run[right_index])\n"
    "            right_index = right_index + 1\n"
    "    merged_output.extend(left_run[left_index:])\n"
    "    merged_output.extend(right_run[right_index:])\n"
    "    return merged_output\n"
    "\n"
    "\n"
    "def galloping_search_bound(sequence_value, target_key, start_hint, step_size):\n"
    "    probe_offset = 1\n"
    "    while start_hint + probe_offset < len(sequence_value):\n"
    "        if sequence_value[start_hint + probe_offset] >= target_key:\n"
    "            return start_hint + probe_offset\n"
    "        probe_offset = probe_offset * step_size\n"
    "    return len(sequence_value)\n"
)

UNRELATED_CODE = (
    "class TotallyDifferentThing:\n"
    "    def compute_checksum_of_payload(self, payload_bytes, seed_value):\n"
    "        accumulator_state = seed_value\n"
    "        for single_byte in payload_bytes:\n"
    "            accumulator_state = accumulator_state * 31 + single_byte\n"
    "        return accumulator_state % 4294967296\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(value):
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(vars(value))


def window_hashes(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_spec_corpus(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "A small fixture component.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\nThe widget MUST merge two sorted runs.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\nCovers: R-WIDGET-001\n\n"
        "Given two sorted runs\nWhen they are merged\nThen the output is sorted\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n`merge_sorted_runs(left, right, cmp)`\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** - a fixture.\n")


def write_corpus(repo_root, hashes, threshold):
    corpus = {
        "corpus_version": 3,
        "block_threshold": threshold,
        "entries": [
            {
                "reference_id": "ref-licensed-001",
                "license_family": "gpl-3.0",
                "risk_tier": "high",
                "hashes": hashes,
            }
        ],
    }
    path = repo_root / "corpus" / "reference.json"
    write(path, json.dumps(corpus))
    return path


def write_fakes(repo_root, log_path, code):
    gen = repo_root / "gen"
    header = "import json\nimport types\nimport dataclasses\nfrom pathlib import Path\n\nLOG = " + repr(str(log_path)) + "\n\n" + (
        "def _log(name):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n\n"
    )

    write(
        gen / "provenance-checker" / "provenance_checker.py",
        header
        + "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key')\n"
        "    return None\n\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key')\n"
        "    return types.SimpleNamespace(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:' + 'a' * 64,\n"
        "        gate_versions={'license_scanner': 'license_scanner@4.0.3', 'secret_scanner': 'secret_scanner@3.1.0'},\n"
        "        spec_bundle_parts={'spec': 'sha256:' + 'b' * 64, 'dependency_code': 'sha256:' + 'c' * 64},\n"
        "    )\n\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance')\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None, 'manifest': None}\n",
    )

    write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        header
        + "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    _log('assemble')\n"
        "    return {'component_id': component_id, 'mode': mode,\n"
        "            'spec_bundle_hash': 'sha256:' + 'a' * 64, 'files': {}}\n",
    )

    write(
        gen / "generation-loop" / "generation_loop.py",
        header
        + "CODE = " + repr(code) + "\n\n"
        "def make_closures(model, seed, repo_root, llm_backend):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': ''}\n"
        "    return test_author, judge\n\n"
        "def run_attempts(component_id, bundle, repo_root, model, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts')\n"
        "    slug = component_id[len('comp-'):]\n"
        "    target = Path(repo_root) / 'gen' / slug / (slug.replace('-', '_') + '.py')\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    target.write_text(CODE, encoding='utf-8')\n"
        "    generation_result = {\n"
        "        'component_id': component_id,\n"
        "        'files': {'gen/' + slug + '/' + slug.replace('-', '_') + '.py': CODE},\n"
        "        'spec_bundle_hash': 'sha256:' + 'a' * 64,\n"
        "        'model': model,\n"
        "        'prompt_version': 'v1',\n"
        "        'retry_feedback': ['R-WIDGET-001'],\n"
        "        'generation': {'mode': mode, 'generator_version': 'generator@3.0.0+v11',\n"
        "                       'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None},\n"
        "        'model_call_error': None,\n"
        "        'refused': False,\n"
        "    }\n"
        "    verification_report = {\n"
        "        'component_id': component_id,\n"
        "        'overall': 'pass',\n"
        "        'run_id': 'run-2',\n"
        "        'verification_run_id': 'run-2',\n"
        "        'criteria': [{'criterion_id': 'AC-WIDGET-001', 'covers': ['R-WIDGET-001'],\n"
        "                      'kind': 'generated-test', 'result': 'pass'}],\n"
        "        'mutation_score': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "    }\n"
        "    attempts = [\n"
        "        {'number': 1, 'outcome': 'verification_failed', 'retry_feedback': [],\n"
        "         'error_category': None, 'failed_requirements': ['R-WIDGET-001'], 'transcript_sha256': None},\n"
        "        {'number': 2, 'outcome': 'passed', 'retry_feedback': ['R-WIDGET-001'],\n"
        "         'error_category': None, 'failed_requirements': [], 'transcript_sha256': None},\n"
        "    ]\n"
        "    return {'passed': True, 'stop_reason': 'passed', 'generation_result': generation_result,\n"
        "            'verification_report': verification_report, 'surface_report': None,\n"
        "            'attempts': attempts}\n",
    )

    write(
        gen / "provenance-tracker" / "provenance_tracker.py",
        header
        + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record')\n"
        "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
        "    d.mkdir(parents=True, exist_ok=True)\n"
        "    n = len(list(d.iterdir())) + 1\n"
        "    (d / (str(n) + '.json')).write_text('{}', encoding='utf-8')\n\n"
        "def _repo_root(args, kwargs):\n"
        "    if 'repo_root' in kwargs:\n"
        "        return Path(kwargs['repo_root'])\n"
        "    for a in args:\n"
        "        if isinstance(a, Path) or (isinstance(a, str) and Path(a).is_dir()):\n"
        "            return Path(a)\n"
        "    return Path('.')\n\n"
        "def check_readiness(*args, **kwargs):\n"
        "    _log('check_readiness')\n"
        "    root = _repo_root(args, kwargs)\n"
        "    components = {}\n"
        "    gen_dir = root / 'gen'\n"
        "    for slug_dir in sorted(gen_dir.iterdir()) if gen_dir.is_dir() else []:\n"
        "        mpath = slug_dir / '.provenance.json'\n"
        "        if not mpath.is_file():\n"
        "            continue\n"
        "        manifest = json.loads(mpath.read_text(encoding='utf-8'))\n"
        "        cid = 'comp-' + slug_dir.name\n"
        "        lic = manifest.get('license_scan')\n"
        "        sec = manifest.get('secret_scan')\n"
        "        components[cid] = {\n"
        "            'component_id': cid,\n"
        "            'ready': not (lic or {}).get('blocked', False),\n"
        "            'provenance_hit': manifest.get('provenance_hit', False),\n"
        "            'verification_report': manifest.get('verification_report'),\n"
        "            'license_scan': lic,\n"
        "            'secret_scan': sec,\n"
        "            'manifest': manifest,\n"
        "        }\n"
        "    capabilities = {\n"
        "        'P-COMPLIANCE-GATE': {'P-COMPLIANCE-GATE': {'overall': 'pass', 'scenarios': []}},\n"
        "    }\n"
        "    ready = all(c['ready'] for c in components.values())\n"
        "    return {'ready': ready, 'overall': 'pass' if ready else 'fail',\n"
        "            'components': components, 'capabilities': capabilities}\n",
    )

    write(
        gen / "secret-scanner" / "secret_scanner.py",
        header
        + "class AllowlistInvalidError(Exception):\n"
        "    pass\n\n"
        "@dataclasses.dataclass\n"
        "class SecretScanResult:\n"
        "    scope: str = 'full'\n"
        "    gate_version: str = 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        "    flagged: bool = False\n"
        "    matches: list = dataclasses.field(default_factory=list)\n"
        "    allowed: list = dataclasses.field(default_factory=list)\n"
        "    unused_allowlist_entries: list = dataclasses.field(default_factory=list)\n"
        "    notified: bool = False\n"
        "    notification_delivery_error: object = None\n"
        "    cache_hit: bool = False\n"
        "    def to_dict(self):\n"
        "        return dataclasses.asdict(self)\n\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return SecretScanResult()\n\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return SecretScanResult(scope='precommit')\n\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )

    write(
        gen / "cache-manager" / "cache_manager.py",
        header
        + "@dataclasses.dataclass(frozen=True)\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: object = None\n\n"
        "@dataclasses.dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n\n"
        "@dataclasses.dataclass\n"
        "class Miss:\n"
        "    reason: str = 'not-found'\n"
        "    payload: object = None\n\n"
        "def get(cache_key, repo_root=None):\n"
        "    _log('cache_get')\n"
        "    return Miss()\n\n"
        "def put(cache_key, cached_result, repo_root=None):\n"
        "    _log('cache_put')\n"
        "    return None\n",
    )


def setup_repo(tmp_path, monkeypatch, code, corpus_hashes, threshold):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_spec_corpus(repo_root)
    write_fakes(repo_root, log_path, code)
    corpus_path = write_corpus(repo_root, corpus_hashes, threshold)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    return repo_root, log_path


def read_manifests(repo_root):
    out = []
    for base in ("gen", "verification"):
        path = repo_root / base / SLUG / ".provenance.json"
        assert path.is_file(), "missing provenance manifest at " + str(path)
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def run_cli_exit(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = license_scanner.main(argv)
        except SystemExit as exc:
            rc = exc.code
    return rc, buf.getvalue()


def test_licensed_code_blocks_merge_is_recorded_and_surfaces_after_retry(tmp_path, monkeypatch):
    repo_root, log_path = setup_repo(
        tmp_path, monkeypatch, LICENSED_CODE, window_hashes(LICENSED_CODE), 0.5
    )

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert "run_attempts" in calls
    assert "secret_scan" in calls

    # A retry happened in generation and resolved the attempt-level failure.
    attempts = field(result, "attempts")
    assert [field(a, "outcome") for a in attempts] == ["verification_failed", "passed"]
    assert field(result, "provenance_hit") is False

    # The license scan flagged the licensed code: the merge is blocked.
    lic = field(result, "license_scan")
    assert field(lic, "evaluated") is True
    assert field(lic, "blocked") is True
    assert field(lic, "similarity_score") >= field(lic, "block_threshold")
    assert any(field(m, "reference_id") == "ref-licensed-001" for m in field(lic, "matches"))

    rc, out = run_cli_exit([COMPONENT_ID, "--repo-root=" + str(repo_root), "--format=json"])
    assert rc == 1, out

    # Written into both provenance manifests' license_scan field.
    for manifest in read_manifests(repo_root):
        assert "license_scan" in manifest
        recorded = manifest["license_scan"]
        assert recorded["component_id"] == COMPONENT_ID
        assert recorded["evaluated"] is True
        assert recorded["blocked"] is True
        assert any(m["reference_id"] == "ref-licensed-001" for m in recorded["matches"])
        assert [a["outcome"] for a in manifest["attempt_history"]] == ["verification_failed", "passed"]

    # The finding appears in the review packet despite the retry having passed.
    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    compliance = field(packet, "compliance_flags")
    license_flags = field(compliance, "license_scan")
    assert isinstance(field(compliance, "secret_scan"), list)
    entries = [e for e in license_flags if field(e, "component_id") == COMPONENT_ID]
    assert entries, "license finding missing from review packet: " + repr(license_flags)
    flagged = as_plain(field(entries[0], "result"))
    assert flagged["blocked"] is True


def test_clean_license_scan_is_still_written_to_manifest(tmp_path, monkeypatch):
    repo_root, log_path = setup_repo(
        tmp_path, monkeypatch, LICENSED_CODE, window_hashes(UNRELATED_CODE), 0.5
    )

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    lic = field(result, "license_scan")
    assert field(lic, "evaluated") is True
    assert field(lic, "blocked") is False

    for manifest in read_manifests(repo_root):
        assert "license_scan" in manifest
        recorded = manifest["license_scan"]
        assert recorded is not None
        assert recorded["component_id"] == COMPONENT_ID
        assert recorded["evaluated"] is True
        assert recorded["blocked"] is False