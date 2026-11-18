# hotdocs-criterion: sha256:38c8fa70fc00ea39eced834b56f811979a59bd499dd5b20948d0cf6d190c88b8
"""CS-COMPLIANCE-001 (P-COMPLIANCE-GATE).

Given generated code that matches a known-licensed-code fingerprint above the
similarity threshold, when the pipeline's license scan runs, then the merge is
blocked, the result is written into the provenance manifest's license_scan
field regardless of outcome, and the finding appears in the review packet even
if a subsequent retry resolves it.
"""

import dataclasses
import hashlib
import json
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
REFERENCE_ID = "ref-gpl-001"
SPEC_BUNDLE_HASH = "sha256:" + "0" * 64
CORPUS_REL = "license-corpus.json"
CODE_RELS = ("gen/foo/foo_core.py", "legacy/foo/foo_core.py")

LICENSED_CODE = "\n".join([
    "def accumulate_weighted_total(records, weights, offset):",
    "    running_total = offset",
    "    for index, record in enumerate(records):",
    "        factor = weights[index % len(weights)]",
    "        running_total = running_total + record.amount * factor",
    "        if running_total > record.ceiling:",
    "            running_total = record.ceiling - record.penalty",
    "    return running_total",
    "",
    "",
    "def normalize_vector_entries(vector, scale_divisor):",
    "    magnitude = sum(entry * entry for entry in vector) ** 0.5",
    "    if magnitude == 0:",
    "        return [0 for entry in vector]",
    "    return [entry / (magnitude * scale_divisor) for entry in vector]",
    "",
])

CLEAN_CODE = "\n".join([
    "class Greeter:",
    "    def __init__(self, salutation):",
    "        self.salutation = salutation",
    "",
    "    def greet(self, person_name):",
    "        return self.salutation + person_name",
    "",
])


# ---------------------------------------------------------------- helpers


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if value is None:
        return None
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        value = value.to_dict()
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    return json.loads(json.dumps(value, default=str))


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        joined = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


def src(*lines):
    return "\n".join(lines) + "\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root), check=True, capture_output=True,
    )


def read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def call_main(fn, argv):
    try:
        code = fn(argv)
    except SystemExit as exc:
        code = exc.code
    return 0 if code is None else code


LOG_HELPER = src(
    "import os",
    "",
    "def _log(line):",
    "    p = os.environ.get(" + repr("HOTDOCS_TEST_LOG") + ")",
    "    if p:",
    "        with open(p, 'a', encoding='utf-8') as fh:",
    "            fh.write(line)",
    "            fh.write(chr(10))",
)


# ---------------------------------------------------------------- fakes


def fake_cache_manager():
    return LOG_HELPER + src(
        "from dataclasses import dataclass",
        "",
        "@dataclass",
        "class CacheKey:",
        "    spec_bundle_hash: object = None",
        "    gate_inputs_hash: object = None",
        "    gate_version: object = None",
        "    model_pin: object = None",
        "",
        "@dataclass",
        "class CachedResult:",
        "    gate_type: str = ''",
        "    payload: object = None",
        "    stored_at: str = ''",
        "",
        "def get(cache_key, repo_root=None):",
        "    _log('cache_manager.get')",
        "    return None",
        "",
        "def put(cache_key, cached_result, repo_root=None):",
        "    _log('cache_manager.put')",
        "    return None",
    )


def fake_provenance_checker():
    return LOG_HELPER + src(
        "COMPONENT_ID = " + repr(COMPONENT_ID),
        "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH),
        "",
        "def current_sealed_key(component_id, repo_root):",
        "    _log('provenance_checker.current_sealed_key')",
        "    return None",
        "",
        "def current_provenance_key(component_id, repo_root):",
        "    _log('provenance_checker.current_provenance_key')",
        "    return {",
        "        'component_id': component_id,",
        "        'spec_bundle_hash': SPEC_BUNDLE_HASH,",
        "        'gate_versions': {'license_scanner': 'license_scanner@4.0.3', 'secret_scanner': 'secret_scanner@3.1.0'},",
        "    }",
        "",
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):",
        "    _log('provenance_checker.check_provenance')",
        "    return {",
        "        'component_id': component_id,",
        "        'hit': False,",
        "        'reason': 'no-manifest',",
        "        'verification': None,",
        "        'license_scan': None,",
        "        'secret_scan': None,",
        "    }",
    )


def fake_spec_bundle_assembler():
    return LOG_HELPER + src(
        "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH),
        "",
        "def assemble(component_id, repo_root=None, mode='cold'):",
        "    _log('spec_bundle_assembler.assemble')",
        "    return {",
        "        'component_id': component_id,",
        "        'mode': mode,",
        "        'files': [],",
        "        'dependency_interfaces': [],",
        "        'spec_bundle_hash': SPEC_BUNDLE_HASH,",
        "    }",
    )


def fake_generator():
    return LOG_HELPER + src(
        "from pathlib import Path",
        "",
        "LICENSED = " + repr(LICENSED_CODE),
        "CLEAN = " + repr(CLEAN_CODE),
        "CODE_RELS = " + repr(CODE_RELS),
        "",
        "def generate(bundle, model, retry_feedback=None, repo_root=None, llm_backend=None):",
        "    root = Path(repo_root)",
        "    text = CLEAN if retry_feedback else LICENSED",
        "    _log('generator.generate retry=' + ','.join(retry_feedback or []))",
        "    for rel in CODE_RELS:",
        "        target = root / rel",
        "        target.parent.mkdir(parents=True, exist_ok=True)",
        "        target.write_text(text, encoding='utf-8')",
        "    return {",
        "        'component_id': bundle['component_id'] if isinstance(bundle, dict) else getattr(bundle, 'component_id'),",
        "        'model': model,",
        "        'model_pin': model,",
        "        'prompt_version': 'v1',",
        "        'retry_feedback': list(retry_feedback) if retry_feedback else None,",
        "        'files': [CODE_RELS[0]],",
        "        'model_call_error': None,",
        "        'refused': None,",
        "        'generated_at': '2026-01-01T00:00:00Z',",
        "    }",
    )


def fake_verifier_orchestrator():
    return LOG_HELPER + src(
        "def verify(component_id, repo_root, judge=None, test_author=None):",
        "    _log('verifier_orchestrator.verify')",
        "    return {",
        "        'component_id': component_id,",
        "        'run_id': 'run-1',",
        "        'verification_run_id': 'run-1',",
        "        'overall': 'pass',",
        "        'criteria': [",
        "            {'criterion_id': 'AC-FOO-001', 'result': 'pass', 'failure_origin': None, 'failure_detail': None},",
        "        ],",
        "        'mutation_score': 1.0,",
        "        'mutation_error': None,",
        "    }",
    )


def fake_secret_scanner():
    return LOG_HELPER + src(
        "import dataclasses",
        "from dataclasses import dataclass, field",
        "",
        "@dataclass",
        "class SecretScanResult:",
        "    scope: str = 'full'",
        "    gate_version: str = 'secret_scanner@3.1.0+detect-secrets.1.5.0'",
        "    flagged: bool = False",
        "    matches: list = field(default_factory=list)",
        "    allowed: list = field(default_factory=list)",
        "    unused_allowlist_entries: list = field(default_factory=list)",
        "    notified: bool = False",
        "    notification_delivery_error: object = None",
        "    cache_hit: bool = False",
        "",
        "    def to_dict(self):",
        "        return dataclasses.asdict(self)",
        "",
        "def scan(repo_root):",
        "    _log('secret_scanner.scan')",
        "    return SecretScanResult()",
        "",
        "def scan_files(paths, repo_root=None):",
        "    _log('secret_scanner.scan_files')",
        "    return SecretScanResult(scope='precommit')",
        "",
        "def gate_version(repo_root):",
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'",
    )


def fake_provenance_tracker(verify_report):
    return LOG_HELPER + src(
        "from pathlib import Path",
        "import json",
        "",
        "REPORT = " + repr(verify_report),
        "",
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):",
        "    _log('provenance_tracker.write_attempt_record')",
        "    slug = component_id[len('comp-'):]",
        "    d = Path(repo_root) / '.hotdocs' / 'attempts' / slug",
        "    d.mkdir(parents=True, exist_ok=True)",
        "    n = len(list(d.iterdir())) + 1",
        "    p = d / ('attempt-' + str(n) + '.json')",
        "    p.write_text(json.dumps({'component_id': component_id, 'attempt': n, 'spec_bundle_hash': spec_bundle_hash}), encoding='utf-8')",
        "    return {'component_id': component_id, 'attempt': n, 'path': str(p.relative_to(Path(repo_root)))}",
        "",
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):",
        "    _log('provenance_tracker.check_readiness')",
        "    return REPORT",
        "",
        "def last_requirement_failures(component_id, repo_root):",
        "    return []",
    )


# ---------------------------------------------------------------- fixture


def build_repo(repo_root, licensed_hashes):
    write(repo_root / "specs" / "components" / SLUG / "component.md", src(
        "---",
        "id: " + COMPONENT_ID,
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team]",
        "sealed: true",
        "source_path: legacy/foo/",
        "---",
        "",
        "# Foo",
        "",
        "A fixture component for the compliance gate.",
    ))
    write(repo_root / "specs" / "components" / SLUG / "requirements" / "R-FOO-001.md", src(
        "# R-FOO-001",
        "",
        "Foo MUST compute totals.",
    ))
    write(repo_root / "specs" / "components" / SLUG / "acceptance" / "AC-FOO-001.md", src(
        "# AC-FOO-001",
        "Covers: R-FOO-001",
        "",
        "Given records, when totals are computed, then a number is returned.",
    ))
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {"reference_id": REFERENCE_ID, "license_family": "GPL", "risk_tier": "high",
             "hashes": sorted(licensed_hashes)},
        ],
    }
    write(repo_root / CORPUS_REL, json.dumps(corpus, indent=2))
    for rel in CODE_RELS:
        write(repo_root / rel, LICENSED_CODE)
    write(repo_root / "gen" / "cache-manager" / "cache_manager.py", fake_cache_manager())
    write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", fake_provenance_checker())
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", fake_spec_bundle_assembler())
    write(repo_root / "gen" / "generator" / "generator.py", fake_generator())
    write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", fake_verifier_orchestrator())
    write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", fake_secret_scanner())


def assert_blocked_license(result):
    assert field(result, "evaluated") is True
    assert field(result, "blocked") is True
    score = field(result, "similarity_score")
    threshold = field(result, "block_threshold")
    assert score is not None and threshold is not None
    assert score >= threshold
    ref_ids = [field(m, "reference_id") for m in field(result, "matches")]
    assert REFERENCE_ID in ref_ids


def read_manifest(path):
    assert path.is_file(), "provenance manifest missing at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- test


def test_cs_compliance_001_license_flag_blocks_is_recorded_and_survives_retry(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    licensed_hashes = window_hashes(LICENSED_CODE)
    assert licensed_hashes
    assert not (window_hashes(CLEAN_CODE) & licensed_hashes)

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", CORPUS_REL)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))

    build_repo(repo_root, licensed_hashes)

    # When the license scan runs over the licensed-looking generated code,
    # the merge is blocked: the result is blocked and the CLI exits 1.
    direct = license_scanner.scan(COMPONENT_ID, repo_root)
    assert_blocked_license(direct)
    exit_code = call_main(license_scanner.main, [COMPONENT_ID, "--repo-root", str(repo_root), "--format", "json"])
    capsys.readouterr()
    assert exit_code == 1

    blocked_scan = to_plain(direct)
    verify_report = {
        "ready": False,
        "blocked": True,
        "components": [
            {
                "component_id": COMPONENT_ID,
                "provenance_hit": False,
                "verification": {
                    "component_id": COMPONENT_ID,
                    "overall": "pass",
                    "criteria": [{"criterion_id": "AC-FOO-001", "result": "pass",
                                  "failure_origin": None, "failure_detail": None}],
                    "mutation_score": 1.0,
                    "mutation_error": None,
                },
                "license_scan": blocked_scan,
                "secret_scan": {
                    "scope": "full", "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
                    "flagged": False, "matches": [], "allowed": [], "unused_allowlist_entries": [],
                    "notified": False, "notification_delivery_error": None, "cache_hit": False,
                },
            },
        ],
        "capabilities": {},
        "blocking_reasons": [{"component_id": COMPONENT_ID, "gate": "license_scan"}],
    }
    write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", fake_provenance_tracker(verify_report))

    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "fixture")

    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"

    # First pipeline run: generated code matches the licensed fingerprint.
    first = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "test-model", seed=0)
    assert field(first, "provenance_hit") is False
    assert_blocked_license(field(first, "license_scan"))

    for manifest_path in (gen_manifest, ver_manifest):
        manifest = read_manifest(manifest_path)
        assert "license_scan" in manifest
        assert manifest["license_scan"] is not None
        assert_blocked_license(manifest["license_scan"])

    # Retry with feedback: the regenerated code no longer matches.
    second = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "test-model", seed=0, retry_feedback=["R-FOO-001"],
    )
    second_scan = field(second, "license_scan")
    assert field(second_scan, "evaluated") is True
    assert field(second_scan, "blocked") is False

    # The result is written regardless of outcome: the clean result too.
    for manifest_path in (gen_manifest, ver_manifest):
        manifest = read_manifest(manifest_path)
        assert "license_scan" in manifest
        assert manifest["license_scan"] is not None
        assert manifest["license_scan"]["evaluated"] is True
        assert manifest["license_scan"]["blocked"] is False

    calls = read_log(log_path)
    generator_calls = [c for c in calls if c.startswith("generator.generate")]
    assert generator_calls == ["generator.generate retry=", "generator.generate retry=R-FOO-001"]

    # The finding still appears in the review packet after the retry resolved it.
    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    compliance = field(packet, "compliance_flags")
    license_entries = field(compliance, "license_scan")
    ours = [e for e in license_entries if field(e, "component_id") == COMPONENT_ID]
    assert ours, "license finding for " + COMPONENT_ID + " missing from the review packet"
    entry_result = field(ours[0], "result")
    assert field(entry_result, "blocked") is True
    ref_ids = [field(m, "reference_id") for m in field(entry_result, "matches")]
    assert REFERENCE_ID in ref_ids