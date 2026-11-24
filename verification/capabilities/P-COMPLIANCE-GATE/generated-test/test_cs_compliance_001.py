# hotdocs-criterion: sha256:67812fa09afa81593010d73646ce497ff4297a8ff501dc7b07d4eb4f1b600ff2
"""CS-COMPLIANCE-001: licensed-code risk never reaches main silently.

Generated code that matches a known-licensed-code fingerprint above the
similarity threshold makes the license scan block. The scan result is
written into the provenance manifest's ``license_scan`` field whatever the
outcome. The finding also appears in the review packet even after a later
retry resolves it.
"""

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import component_gate_runner
import license_scanner
import provenance_writer
import review_packet_builder
import secret_scanner


COMPONENT_ID = "comp-foo"
SLUG = "foo"
SBH = "sha256:" + "ab" * 32
GATE_VERSIONS = {"compiler": "1.0.0", "license_scanner": "license_scanner@4.0.3", "secret_scanner": "secret_scanner@3.1.0"}

LICENSED_CODE = (
    "def compute_weighted_total(items, rate, offset):\n"
    "    total = 0\n"
    "    for item in items:\n"
    "        total = total + item * rate + offset\n"
    "    return total\n"
    "\n"
    "\n"
    "def compute_average_value(values, count, scale):\n"
    "    accumulator = 0\n"
    "    for value in values:\n"
    "        accumulator = accumulator + value * scale\n"
    "    return accumulator / count\n"
)

CLEAN_CODE = (
    "class Greeter:\n"
    "    def __init__(self, name):\n"
    "        self.name = name\n"
    "\n"
    "    def greet(self):\n"
    "        return 'hello ' + self.name\n"
    "\n"
    "    def shout(self):\n"
    "        return self.greet().upper() + ' and welcome along'\n"
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


LOG_HELPER = (
    "import os\n"
    "\n"
    "def _log(line):\n"
    "    with open(os.environ['HOTDOCS_TEST_LOG'], 'a') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
)


def provenance_checker_source():
    return (
        LOG_HELPER
        + "SBH = " + repr(SBH) + "\n"
        + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        + "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key ' + component_id)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key ' + component_id)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': SBH,\n"
        "            'gate_versions': dict(GATE_VERSIONS)}\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance ' + component_id)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'component_id': component_id,\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    )


def spec_bundle_assembler_source():
    return (
        LOG_HELPER
        + "SBH = " + repr(SBH) + "\n"
        + "\n"
        "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    _log('assemble ' + component_id + ' ' + mode)\n"
        "    return {'component_id': component_id, 'mode': mode, 'files': {},\n"
        "            'spec_bundle_hash': SBH, 'bundle_hash': SBH}\n"
    )


def generation_loop_source():
    return (
        LOG_HELPER
        + "from pathlib import Path\n"
        + "SBH = " + repr(SBH) + "\n"
        + "SLUG = " + repr(SLUG) + "\n"
        + "\n"
        "def make_closures(model, seed, repo_root, llm_backend):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': ''}\n"
        "    return test_author, judge\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts ' + component_id)\n"
        "    code = Path(os.environ['HOTDOCS_TEST_CODE_PATH']).read_text(encoding='utf-8')\n"
        "    target = Path(repo_root) / 'gen' / SLUG\n"
        "    target.mkdir(parents=True, exist_ok=True)\n"
        "    (target / (SLUG + '.py')).write_text(code, encoding='utf-8')\n"
        "    generation_result = {\n"
        "        'component_id': component_id, 'files': {SLUG + '.py': code},\n"
        "        'spec_bundle_hash': SBH, 'model': model, 'prompt_version': 'v1',\n"
        "        'retry_feedback': retry_feedback, 'mode': mode,\n"
        "        'generator_version': 'generator@3.0.0+v11', 'transcript_sha256': None,\n"
        "        'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
        "        'model_call_error': None, 'refused': False,\n"
        "    }\n"
        "    verification_report = {\n"
        "        'component_id': component_id, 'overall': 'pass', 'run_id': 'run-1',\n"
        "        'criteria': [{'criterion_id': 'AC-FOO-001', 'result': 'pass'}],\n"
        "        'assets': [],\n"
        "    }\n"
        "    attempts = [{'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
        "                 'error_category': None, 'failed_requirements': [],\n"
        "                 'transcript_sha256': None}]\n"
        "    return {'passed': True, 'attempts': attempts,\n"
        "            'generation_result': generation_result,\n"
        "            'verification_report': verification_report,\n"
        "            'surface_report': None, 'stop_reason': 'passed'}\n"
    )


def secret_scanner_source():
    return (
        LOG_HELPER
        + "from dataclasses import dataclass, field, asdict\n"
        "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "\n"
        "@dataclass\n"
        "class SecretScanResult:\n"
        "    scope: str = 'full'\n"
        "    gate_version: str = 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        "    flagged: bool = False\n"
        "    matches: list = field(default_factory=list)\n"
        "    allowed: list = field(default_factory=list)\n"
        "    unused_allowlist_entries: list = field(default_factory=list)\n"
        "    notified: bool = False\n"
        "    notification_delivery_error: object = None\n"
        "    cache_hit: bool = False\n"
        "\n"
        "    def to_dict(self):\n"
        "        return asdict(self)\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return SecretScanResult()\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return SecretScanResult(scope='precommit')\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )


def cache_manager_source():
    return (
        LOG_HELPER
        + "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: object = None\n"
        "    gate_inputs_hash: object = None\n"
        "    gate_version: object = None\n"
        "    model_pin: object = None\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str = ''\n"
        "    payload: object = None\n"
        "    stored_at: str = ''\n"
        "\n"
        "class Miss:\n"
        "    payload = None\n"
        "    reason = 'absent'\n"
        "\n"
        "def get(cache_key, repo_root=None):\n"
        "    _log('cache_get')\n"
        "    return Miss()\n"
        "\n"
        "def put(cache_key, cached_result, repo_root=None):\n"
        "    _log('cache_put')\n"
        "    return None\n"
    )


def provenance_tracker_source(report):
    return (
        LOG_HELPER
        + "REPORT = " + repr(report) + "\n"
        + "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return REPORT\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record ' + component_id)\n"
        "    return None\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root), check=True, capture_output=True,
    )


def build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write(
        repo_root / "specs" / "components" / SLUG / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "Computes weighted totals.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\nFoo computes a weighted total of its items.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\n\nGiven items, when totalled, then the weighted total is returned.\n",
    )
    gen = repo_root / "gen"
    write(gen / "provenance-checker" / "provenance_checker.py", provenance_checker_source())
    write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", spec_bundle_assembler_source())
    write(gen / "generation-loop" / "generation_loop.py", generation_loop_source())
    write(gen / "secret-scanner" / "secret_scanner.py", secret_scanner_source())
    write(gen / "cache-manager" / "cache_manager.py", cache_manager_source())
    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "fixture")
    return repo_root


def read_manifest(repo_root, area):
    path = repo_root / area / SLUG / ".provenance.json"
    assert path.is_file(), "missing provenance manifest at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def test_cs_compliance_001(tmp_path, monkeypatch):
    repo_root = build_repo(tmp_path)
    log_path = tmp_path / "calls.log"
    code_path = tmp_path / "code" / "candidate.py"
    corpus_path = tmp_path / "corpus" / "reference-corpus.json"

    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-gpl-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": window_hashes(LICENSED_CODE),
            }
        ],
    }
    assert corpus["entries"][0]["hashes"], "fixture code must yield 9-token windows"
    write(corpus_path, json.dumps(corpus))
    write(code_path, LICENSED_CODE)

    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))
    monkeypatch.setenv("HOTDOCS_TEST_CODE_PATH", str(code_path))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    # --- First run: generated code matches the licensed fingerprint ---
    result1 = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "anthropic:claude-sonnet-5"
    )
    scan1 = field(result1, "license_scan")
    assert field(scan1, "evaluated") is True
    assert field(scan1, "similarity_score") >= field(scan1, "block_threshold")
    assert field(scan1, "blocked") is True, "a licensed-code match above threshold must block the merge"
    matches1 = field(scan1, "matches")
    assert matches1, "a flagged result always carries its matches"
    assert any(field(m, "reference_id") == "ref-gpl-001" for m in matches1)

    log_text = log_path.read_text(encoding="utf-8")
    assert "run_attempts comp-foo" in log_text
    assert "secret_scan" in log_text

    for area in ("gen", "verification"):
        manifest1 = read_manifest(repo_root, area)
        assert "license_scan" in manifest1
        assert manifest1["license_scan"]["blocked"] is True
        assert manifest1["license_scan"]["evaluated"] is True
        assert manifest1["license_scan"]["similarity_score"] == field(scan1, "similarity_score")
        assert any(m["reference_id"] == "ref-gpl-001" for m in manifest1["license_scan"]["matches"])
    blocked_scan = read_manifest(repo_root, "gen")["license_scan"]

    # --- Retry: regenerated code no longer matches; the scan resolves ---
    write(code_path, CLEAN_CODE)
    result2 = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "anthropic:claude-sonnet-5"
    )
    scan2 = field(result2, "license_scan")
    assert field(scan2, "evaluated") is True
    assert field(scan2, "blocked") is False
    assert field(scan2, "similarity_score") < field(scan2, "block_threshold")

    for area in ("gen", "verification"):
        manifest2 = read_manifest(repo_root, area)
        assert "license_scan" in manifest2, "license_scan is written regardless of outcome"
        assert manifest2["license_scan"]["blocked"] is False
        assert manifest2["license_scan"]["evaluated"] is True

    # --- Review packet: the earlier finding is still surfaced ---
    verification_report = {
        "component_id": COMPONENT_ID, "overall": "pass", "run_id": "run-1",
        "criteria": [{"criterion_id": "AC-FOO-001", "result": "pass"}],
        "assets": [],
    }
    secret_clean = {
        "scope": "full", "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False, "matches": [], "allowed": [], "unused_allowlist_entries": [],
        "notified": False, "notification_delivery_error": None, "cache_hit": False,
    }
    verify_report = {
        "ready": False,
        "blocking": [{"component_id": COMPONENT_ID, "reason": "license_scan_blocked"}],
        "components": {
            COMPONENT_ID: {
                "component_id": COMPONENT_ID,
                "ready": False,
                "blocked": True,
                "provenance_hit": False,
                "verification_report": verification_report,
                "license_scan": blocked_scan,
                "secret_scan": secret_clean,
                "reasons": ["license_scan_blocked"],
            }
        },
        "capabilities": {},
    }
    assert isinstance(verify_report["components"], dict)
    assert isinstance(verify_report["capabilities"], dict)
    write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        provenance_tracker_source(verify_report),
    )

    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    flags = field(packet, "compliance_flags")
    license_flags = field(flags, "license_scan")
    secret_flags = field(flags, "secret_scan")
    assert isinstance(license_flags, list)
    assert isinstance(secret_flags, list)
    entries = [e for e in license_flags if field(e, "component_id") == COMPONENT_ID]
    assert entries, "the license finding must appear in the review packet even after a retry resolved it"
    flagged_result = field(entries[0], "result")
    assert field(flagged_result, "blocked") is True
    assert field(flagged_result, "similarity_score") >= field(flagged_result, "block_threshold")