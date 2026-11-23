# hotdocs-criterion: sha256:7ae8ed3eeda2683207fb1725f9428d4ba58bf5152a737732fd742bfacf73a975
import component_gate_runner
import license_scanner
import provenance_writer
import review_packet_builder
import secret_scanner

import dataclasses
import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path


COMPONENT_ID = "comp-licensed"
SLUG = "licensed"
LOG_ENV = "HOTDOCS_CS_COMPLIANCE_LOG"
CODE_ENV = "HOTDOCS_CS_COMPLIANCE_CODE"
SPEC_BUNDLE_HASH = "sha256:" + ("0" * 64)
MODEL = "anthropic:claude-sonnet-5"
REFERENCE_ID = "ref-gpl-001"

LICENSED_CODE = (
    "def gcd_table(limit):\n"
    "    table = []\n"
    "    for left in range(1, limit):\n"
    "        row = []\n"
    "        for right in range(1, limit):\n"
    "            a = left\n"
    "            b = right\n"
    "            while b:\n"
    "                a, b = b, a % b\n"
    "            row.append(a)\n"
    "        table.append(row)\n"
    "    return table\n"
)

RESOLVED_CODE = (
    "def total(values):\n"
    "    acc = 0\n"
    "    for item in values:\n"
    "        acc = acc + item\n"
    "    return acc\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plain(value):
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return plain(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return plain(dataclasses.asdict(value))
    return value


def window_hashes(code):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", code)]
    hashes = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


LOG_HELPER = (
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(line):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root), check=True, capture_output=True,
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "components" / SLUG / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Licensed Fixture\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Licensed Fixture\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "requirements" / "R-LICENSED-001.md",
        "# R-LICENSED-001\n\nThe component computes a table.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "acceptance" / "AC-LICENSED-001.md",
        "# AC-LICENSED-001\n\nCovers: R-LICENSED-001\n\nThe table is computed.\n",
    )
    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "fixture")


def write_pipeline_fakes(repo_root):
    gate_versions = {"compiler": "1.0.0"}
    write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        LOG_HELPER
        + "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key')\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key')\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': "
        + repr(SPEC_BUNDLE_HASH) + ", 'gate_versions': " + repr(gate_versions) + "}\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance')\n"
        "    return {'component_id': component_id, 'hit': False, 'reason': 'no manifest',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None}\n",
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        LOG_HELPER
        + "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    _log('assemble')\n"
        "    return {'component_id': component_id, 'mode': mode, 'spec_bundle_hash': "
        + repr(SPEC_BUNDLE_HASH) + ", 'files': {}}\n",
    )
    write(
        repo_root / "gen" / "generation-loop" / "generation_loop.py",
        LOG_HELPER
        + "def make_closures(model, seed, repo_root, llm_backend):\n"
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
        "    _log('run_attempts')\n"
        "    code = Path(os.environ[" + repr(CODE_ENV) + "]).read_text(encoding='utf-8')\n"
        "    target = Path(repo_root) / 'gen' / " + repr(SLUG) + " / " + repr(SLUG + ".py") + "\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    target.write_text(code, encoding='utf-8')\n"
        "    generation_result = {\n"
        "        'component_id': component_id,\n"
        "        'files': {" + repr(SLUG + ".py") + ": code},\n"
        "        'spec_bundle_hash': " + repr(SPEC_BUNDLE_HASH) + ",\n"
        "        'model': model,\n"
        "        'prompt_version': 'v1',\n"
        "        'retry_feedback': None,\n"
        "        'mode': mode,\n"
        "        'generator_version': 'generator@3.0.0+v11',\n"
        "        'transcript_sha256': None,\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "        'model_call_error': None,\n"
        "        'refused': False,\n"
        "    }\n"
        "    verification_report = {\n"
        "        'component_id': component_id,\n"
        "        'overall': 'pass',\n"
        "        'criteria': [{'criterion_id': 'AC-LICENSED-001', 'result': 'pass',\n"
        "                      'failure_detail': None}],\n"
        "        'mutation_score': 1.0,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'run_id': 'run-1',\n"
        "        'verification_run_id': 'run-1',\n"
        "        'verifier_version': 'verifier-orchestrator@2.0.0',\n"
        "    }\n"
        "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
        "               'error_category': None, 'failed_requirements': [],\n"
        "               'transcript_sha256': None}\n"
        "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [attempt],\n"
        "            'generation_result': generation_result,\n"
        "            'verification_report': verification_report,\n"
        "            'surface_report': None}\n",
    )


def write_tracker_stand_in(repo_root, report):
    write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        LOG_HELPER
        + "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return " + repr(report) + "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record')\n"
        "    return None\n",
    )


def read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def test_cs_compliance_001(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    log_path = outside / "calls.log"
    code_path = outside / "generated_source.py"
    code_path.write_text(LICENSED_CODE, encoding="utf-8")

    corpus_path = outside / "corpus.json"
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {"reference_id": REFERENCE_ID, "license_family": "GPL-3.0", "risk_tier": "high",
             "hashes": window_hashes(LICENSED_CODE)},
        ],
    }
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.setenv(CODE_ENV, str(code_path))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("no webhook is configured; urlopen must not be called")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)

    build_fixture(repo_root)
    write_pipeline_fakes(repo_root)

    # When the pipeline's license scan runs
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL, 0, None, None)
    assert "run_attempts" in read_log(log_path)
    assert field(result, "provenance_hit") is False

    license_result = field(result, "license_scan")
    assert field(license_result, "evaluated") is True
    score = field(license_result, "similarity_score")
    threshold = field(license_result, "block_threshold")
    assert score is not None and threshold is not None
    assert score >= threshold
    # Then the merge is blocked
    assert field(license_result, "blocked") is True
    match_ids = [field(m, "reference_id") for m in field(license_result, "matches")]
    assert REFERENCE_ID in match_ids

    # and the result is written into the provenance manifest's license_scan field
    for manifest_path in (
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ):
        assert manifest_path.is_file(), manifest_path
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        written = manifest["license_scan"]
        assert written["blocked"] is True
        assert written["evaluated"] is True
        assert written["similarity_score"] == score
        assert REFERENCE_ID in [m["reference_id"] for m in written["matches"]]

    # A subsequent retry resolves the finding
    (repo_root / "gen" / SLUG / (SLUG + ".py")).write_text(RESOLVED_CODE, encoding="utf-8")
    retry = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(retry, "evaluated") is True
    assert field(retry, "blocked") is False

    # The stand-in tracker's VerifyReport keeps components/capabilities keyed by id
    first_license = plain(license_result)
    report = {
        "ready": False,
        "blockers": [{"component_id": COMPONENT_ID, "reason": "license_scan_blocked"}],
        "components": {
            COMPONENT_ID: {
                "component_id": COMPONENT_ID,
                "regenerated": True,
                "provenance_hit": False,
                "blocked": True,
                "verification_report": plain(field(result, "verification")),
                "license_scan": first_license,
                "secret_scan": plain(field(result, "secret_scan")),
            },
        },
        "capabilities": {},
    }
    write_tracker_stand_in(repo_root, report)

    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    assert "check_readiness" in read_log(log_path)

    # and the finding appears in the review packet even though the retry resolved it
    flags = field(packet, "compliance_flags")
    license_flags = field(flags, "license_scan")
    entries = [e for e in license_flags if field(e, "component_id") == COMPONENT_ID]
    assert len(entries) == 1, license_flags
    flagged = field(entries[0], "result")
    assert field(flagged, "blocked") is True
    assert REFERENCE_ID in [field(m, "reference_id") for m in field(flagged, "matches")]