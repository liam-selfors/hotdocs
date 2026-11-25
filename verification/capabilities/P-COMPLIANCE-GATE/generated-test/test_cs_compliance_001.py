# hotdocs-criterion: sha256:c1b07771662fe21dfd313446d9034b686839de6ff03b544c235ca9a4ea77597a
import dataclasses
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import component_gate_runner
import license_scanner
import provenance_writer
import review_packet_builder
import secret_scanner


COMPONENT_ID = "comp-foo"
SLUG = "foo"
MODEL = "anthropic:claude-sonnet-5"
SPEC_BUNDLE_HASH = "sha256:" + ("ab" * 32)
GATE_VERSIONS = {
    "license_scanner": "license_scanner@4.0.0",
    "secret_scanner": "secret_scanner@3.1.0",
}

GENERATED_CODE = (
    "def accumulate_totals(values, factor):\n"
    "    total = 0\n"
    "    for item in values:\n"
    "        total = total + item * factor\n"
    "    return total\n"
    "\n"
    "\n"
    "def scale_every_value(values, factor, offset):\n"
    "    result = []\n"
    "    for item in values:\n"
    "        result.append(item * factor + offset)\n"
    "    return result\n"
)

VERIFICATION_REPORT = {
    "component_id": COMPONENT_ID,
    "overall": "pass",
    "run_id": "run-1",
    "criteria": [
        {
            "criterion_id": "AC-FOO-001",
            "kind": "generated-test",
            "covers": ["R-FOO-001"],
            "result": "pass",
        }
    ],
    "mutation_score": 1.0,
    "assets": [],
}

GENERATION_RESULT = {
    "component_id": COMPONENT_ID,
    "files": {"gen/foo/foo.py": GENERATED_CODE},
    "spec_bundle_hash": SPEC_BUNDLE_HASH,
    "model": MODEL,
    "prompt_version": "v1",
    "retry_feedback": [],
    "mode": "single",
    "generator_version": "generator@3.0.0+v11",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
    "model_call_error": None,
    "refused": False,
}

ATTEMPTS = [
    {
        "number": 1,
        "outcome": "verification_failed",
        "retry_feedback": [],
        "error_category": None,
        "failed_requirements": ["R-FOO-001"],
        "transcript_sha256": None,
    },
    {
        "number": 2,
        "outcome": "passed",
        "retry_feedback": ["R-FOO-001"],
        "error_category": None,
        "failed_requirements": [],
        "transcript_sha256": None,
    },
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(value):
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return value


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


LOG_PREAMBLE = (
    "import os\n"
    "\n"
    "\n"
    "def _log(name):\n"
    "    with open(os.environ['CS_COMPLIANCE_LOG'], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(name + '\\n')\n"
    "\n"
    "\n"
)


def provenance_checker_source():
    return (
        LOG_PREAMBLE
        + "def current_sealed_key(component_id, repo_root):\n"
        + "    _log('current_sealed_key')\n"
        + "    return None\n"
        + "\n\n"
        + "def current_provenance_key(component_id, repo_root):\n"
        + "    _log('current_provenance_key')\n"
        + "    return {'component_id': component_id, 'spec_bundle_hash': "
        + repr(SPEC_BUNDLE_HASH)
        + ", 'gate_versions': "
        + repr(GATE_VERSIONS)
        + "}\n"
        + "\n\n"
        + "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        + "    _log('check_provenance')\n"
        + "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        + "            'license_scan': None, 'secret_scan': None}\n"
    )


def spec_bundle_assembler_source():
    return (
        LOG_PREAMBLE
        + "def assemble(component_id, repo_root=None, mode='cold'):\n"
        + "    _log('assemble')\n"
        + "    return {'component_id': component_id, 'spec_bundle_hash': "
        + repr(SPEC_BUNDLE_HASH)
        + ", 'mode': mode, 'files': {}}\n"
    )


def generation_loop_source():
    return (
        LOG_PREAMBLE
        + "from pathlib import Path\n"
        + "import copy\n"
        + "\n"
        + "CODE = " + repr(GENERATED_CODE) + "\n"
        + "GENERATION_RESULT = " + repr(GENERATION_RESULT) + "\n"
        + "VERIFICATION_REPORT = " + repr(VERIFICATION_REPORT) + "\n"
        + "ATTEMPTS = " + repr(ATTEMPTS) + "\n"
        + "\n\n"
        + "def make_closures(model, seed, repo_root, llm_backend):\n"
        + "    _log('make_closures')\n"
        + "    def test_author(bundle):\n"
        + "        return {'model_call_error': None, 'file': None}\n"
        + "    def judge(bundle):\n"
        + "        return {'result': 'pass', 'rationale': 'stand-in'}\n"
        + "    return test_author, judge\n"
        + "\n\n"
        + "def run_attempts(component_id, bundle, repo_root, model, mode='single', max_attempts=3,\n"
        + "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        + "                 allow_unisolated_exec=False, on_attempt=None):\n"
        + "    _log('run_attempts')\n"
        + "    root = Path(repo_root)\n"
        + "    target = root / 'gen' / 'foo' / 'foo.py'\n"
        + "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        + "    target.write_text(CODE, encoding='utf-8')\n"
        + "    attempts_dir = root / '.hotdocs' / 'attempts' / component_id\n"
        + "    attempts_dir.mkdir(parents=True, exist_ok=True)\n"
        + "    for entry in ATTEMPTS:\n"
        + "        (attempts_dir / ('attempt-' + str(entry['number']) + '.json')).write_text('{}', encoding='utf-8')\n"
        + "    return {\n"
        + "        'passed': True,\n"
        + "        'stop_reason': 'passed',\n"
        + "        'attempts': copy.deepcopy(ATTEMPTS),\n"
        + "        'generation_result': copy.deepcopy(GENERATION_RESULT),\n"
        + "        'verification_report': copy.deepcopy(VERIFICATION_REPORT),\n"
        + "        'surface_report': None,\n"
        + "    }\n"
    )


def secret_scanner_source():
    return (
        LOG_PREAMBLE
        + "import dataclasses\n"
        + "\n\n"
        + "class AllowlistInvalidError(Exception):\n"
        + "    pass\n"
        + "\n\n"
        + "@dataclasses.dataclass\n"
        + "class SecretScanResult:\n"
        + "    scope: str\n"
        + "    gate_version: str\n"
        + "    flagged: bool\n"
        + "    matches: list\n"
        + "    allowed: list\n"
        + "    unused_allowlist_entries: list\n"
        + "    notified: bool\n"
        + "    notification_delivery_error: object\n"
        + "    cache_hit: bool\n"
        + "\n"
        + "    def to_dict(self):\n"
        + "        return dataclasses.asdict(self)\n"
        + "\n\n"
        + "def _clean(scope):\n"
        + "    return SecretScanResult(scope=scope, gate_version='secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
        + "                            flagged=False, matches=[], allowed=[], unused_allowlist_entries=[],\n"
        + "                            notified=False, notification_delivery_error=None, cache_hit=False)\n"
        + "\n\n"
        + "def scan(repo_root):\n"
        + "    _log('secret_scan')\n"
        + "    return _clean('full')\n"
        + "\n\n"
        + "def scan_files(paths, repo_root=None):\n"
        + "    return _clean('precommit')\n"
        + "\n\n"
        + "def gate_version(repo_root):\n"
        + "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        + "\n\n"
        + "def propose(repo_root):\n"
        + "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )


def cache_manager_source():
    return (
        LOG_PREAMBLE
        + "import dataclasses\n"
        + "\n\n"
        + "@dataclasses.dataclass\n"
        + "class CacheKey:\n"
        + "    spec_bundle_hash: object\n"
        + "    gate_inputs_hash: object\n"
        + "    gate_version: object\n"
        + "    model_pin: object\n"
        + "\n\n"
        + "@dataclasses.dataclass\n"
        + "class CachedResult:\n"
        + "    gate_type: str\n"
        + "    payload: object\n"
        + "    stored_at: str\n"
        + "\n\n"
        + "class Miss:\n"
        + "    payload = None\n"
        + "    reason = 'not-found'\n"
        + "\n\n"
        + "def get(cache_key, repo_root=None):\n"
        + "    _log('cache_get')\n"
        + "    return Miss()\n"
        + "\n\n"
        + "def put(cache_key, cached_result, repo_root=None):\n"
        + "    _log('cache_put')\n"
        + "    return None\n"
    )


def provenance_tracker_source(report):
    return (
        LOG_PREAMBLE
        + "import copy\n"
        + "\n"
        + "REPORT = " + repr(report) + "\n"
        + "\n\n"
        + "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        + "    _log('check_readiness')\n"
        + "    return copy.deepcopy(REPORT)\n"
        + "\n\n"
        + "def last_requirement_failures(component_id, repo_root):\n"
        + "    return []\n"
        + "\n\n"
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        + "                         spec_bundle_hash, repo_root):\n"
        + "    _log('write_attempt_record')\n"
        + "    return None\n"
    )


def verify_report(license_scan, secret_scan):
    return {
        "ready": True,
        "overall": "pass",
        "components": {
            COMPONENT_ID: {
                "component_id": COMPONENT_ID,
                "status": "regenerated",
                "overall": "pass",
                "provenance_hit": False,
                "verification_report": VERIFICATION_REPORT,
                "license_scan": license_scan,
                "secret_scan": secret_scan,
            }
        },
        "capabilities": {},
        "blocking": [],
    }


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "Accumulates totals.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(comp / "interface" / "library.md", "# Library\n\n`accumulate_totals(values, factor)`\n")
    write(comp / "requirements" / "R-FOO-001.md", "# R-FOO-001\n\nTotals are accumulated.\n")
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\n\nGiven values, when totalled, then the sum is returned.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** - a fixture component.\n")
    write(repo_root / "legacy" / "foo" / "README.md", "legacy fixture\n")

    gen = repo_root / "gen"
    write(gen / "provenance-checker" / "provenance_checker.py", provenance_checker_source())
    write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", spec_bundle_assembler_source())
    write(gen / "generation-loop" / "generation_loop.py", generation_loop_source())
    write(gen / "secret-scanner" / "secret_scanner.py", secret_scanner_source())
    write(gen / "cache-manager" / "cache_manager.py", cache_manager_source())
    write(
        gen / "provenance-tracker" / "provenance_tracker.py",
        provenance_tracker_source(verify_report(None, None)),
    )


def git(repo_root, *args):
    subprocess.run(["git", *args], cwd=str(repo_root), check=True, capture_output=True)


def run_cli(main, argv):
    try:
        code = main(argv)
    except SystemExit as exc:
        code = exc.code
    return 0 if code is None else code


def test_cs_compliance_001_licensed_match_blocks_and_is_recorded_and_surfaced(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")

    corpus_path = tmp_path / "corpus.json"
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": window_hashes(GENERATED_CODE),
            }
        ],
    }
    assert len(corpus["entries"][0]["hashes"]) > 0
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("CS_COMPLIANCE_LOG", str(log_path))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    build_fixture(repo_root)
    git(repo_root, "init")
    git(repo_root, "config", "user.email", "fixture@example.invalid")
    git(repo_root, "config", "user.name", "Fixture")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "fixture")

    # When: the pipeline runs, including its license scan.
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert "run_attempts" in calls
    assert "secret_scan" in calls

    # The retry resolved generation/verification; the license flag stays.
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    attempts = field(result, "attempts")
    assert len(attempts) == 2
    assert field(attempts[-1], "outcome") == "passed"

    license_scan = field(result, "license_scan")
    assert field(license_scan, "component_id") == COMPONENT_ID
    assert field(license_scan, "evaluated") is True
    assert field(license_scan, "similarity_score") >= field(license_scan, "block_threshold")
    assert field(license_scan, "blocked") is True
    assert len(field(license_scan, "matches")) >= 1

    # The merge is blocked: the license scan gate exits 1.
    code = run_cli(
        license_scanner.main,
        [COMPONENT_ID, "--repo-root", str(repo_root), "--format=json"],
    )
    capsys.readouterr()
    assert code == 1

    # Then: the result is written into the provenance manifest's license_scan field.
    license_plain = json.loads(json.dumps(as_plain(license_scan)))
    for manifest_path in (
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ):
        assert manifest_path.is_file(), manifest_path
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_ls = manifest["license_scan"]
        assert manifest_ls["blocked"] is True
        assert manifest_ls["component_id"] == COMPONENT_ID
        assert manifest_ls["similarity_score"] == license_plain["similarity_score"]
        assert manifest_ls == license_plain
        assert manifest["attempt_history"][-1]["outcome"] == "passed"

    # The stand-in tracker now reports the component, keyed by id.
    manifest = json.loads((repo_root / "gen" / SLUG / ".provenance.json").read_text(encoding="utf-8"))
    secret_plain = json.loads(json.dumps(as_plain(field(result, "secret_scan"))))
    tracker_dir = repo_root / "gen" / "provenance-tracker"
    shutil.rmtree(tracker_dir / "__pycache__", ignore_errors=True)
    write(
        tracker_dir / "provenance_tracker.py",
        provenance_tracker_source(verify_report(manifest["license_scan"], secret_plain)),
    )

    # And the finding appears in the review packet despite the resolving retry.
    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    flags = field(packet, "compliance_flags")
    license_flags = field(flags, "license_scan")
    assert isinstance(license_flags, list)
    matching = [e for e in license_flags if field(e, "component_id") == COMPONENT_ID]
    assert len(matching) == 1
    assert field(field(matching[0], "result"), "blocked") is True
    assert isinstance(field(flags, "secret_scan"), list)