# hotdocs-criterion: sha256:b84d4359b373131995de10baac33992a4c4b470f3704c0c99a16363fd3fe244a
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

import pytest

import component_gate_runner
import license_scanner
import provenance_writer
import review_packet_builder
import secret_scanner


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain_dict(value, names):
    return {name: field(value, name) for name in names}


LICENSE_FIELDS = [
    "component_id",
    "gate_version",
    "evaluated",
    "reason",
    "similarity_score",
    "block_threshold",
    "blocked",
    "matches",
    "notified",
    "notification_delivery_error",
    "cache_hit",
]

SECRET_FIELDS = [
    "scope",
    "gate_version",
    "flagged",
    "matches",
    "allowed",
    "unused_allowlist_entries",
    "notified",
    "notification_delivery_error",
    "cache_hit",
]


LICENSED_CODE = (
    "def compute_weighted_checksum(values, weights, modulus):\n"
    "    total = 0\n"
    "    for index in range(len(values)):\n"
    "        value = values[index]\n"
    "        weight = weights[index % len(weights)]\n"
    "        total = (total + value * weight) % modulus\n"
    "    if total < 0:\n"
    "        total = total + modulus\n"
    "    return total\n"
    "\n"
    "def reverse_pairs_in_sequence(sequence):\n"
    "    result = list(sequence)\n"
    "    for position in range(0, len(result) - 1, 2):\n"
    "        result[position], result[position + 1] = result[position + 1], result[position]\n"
    "    return result\n"
)

CLEAN_CODE = (
    "class Greeter:\n"
    "    def __init__(self, salutation):\n"
    "        self.salutation = salutation\n"
    "\n"
    "    def greet(self, person):\n"
    "        message = self.salutation + ' ' + person\n"
    "        print(message)\n"
    "        return message\n"
)


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


def call_main(func, argv):
    try:
        code = func(argv)
    except SystemExit as exc:
        code = exc.code
    return 0 if code is None else code


def test_cs_compliance_001(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()

    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("no webhook call expected")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)

    # Minimal spec corpus for the component.
    comp_dir = repo_root / "specs" / "components" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n"
    )

    # Generated code that matches a known-licensed-code fingerprint.
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True)
    code_path = gen_dir / "foo.py"
    code_path.write_text(LICENSED_CODE)

    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.5,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": window_hashes(LICENSED_CODE),
            }
        ],
    }
    corpus_path = corpus_dir / "license-corpus.json"
    corpus_path.write_text(json.dumps(corpus))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "fixture")

    # The pipeline's license scan runs.
    first = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(first, "evaluated") is True
    assert field(first, "similarity_score") >= field(first, "block_threshold")
    # The merge is blocked.
    assert field(first, "blocked") is True
    assert len(field(first, "matches")) >= 1
    assert call_main(license_scanner.main,
                     [COMPONENT_ID, "--repo-root", str(repo_root), "--format", "json"]) == 1

    secret_result = secret_scanner.scan(repo_root)

    def provenance_inputs(license_result):
        return {
            "component_id": COMPONENT_ID,
            "generation_result": {
                "component_id": COMPONENT_ID,
                "files": {},
                "spec_bundle_hash": "sha256:" + "0" * 64,
                "model": "anthropic:claude-sonnet-5",
                "prompt_version": "v1",
                "retry_feedback": None,
                "mode": "single",
                "transcript_sha256": None,
                "turns": 1,
                "tool_calls": 0,
                "isolation": None,
                "model_call_error": {"category": "network", "message": "fixture"},
                "refused": False,
            },
            "verification_report": None,
            "license_scan_result": license_result,
            "secret_scan_result": secret_result,
            "provenance_hit": False,
            "attempts": 1,
            "attempt_history": [
                {"number": 1, "outcome": "model_call_error", "retry_feedback": [],
                 "error_category": "network", "failed_requirements": [],
                 "transcript_sha256": None}
            ],
            "gate_versions": {
                "license_scanner": field(license_result, "gate_version"),
                "secret_scanner": field(secret_result, "gate_version"),
            },
        }

    manifest_path = repo_root / "gen" / SLUG / ".provenance.json"

    provenance_writer.write_provenance(COMPONENT_ID, provenance_inputs(first), repo_root)
    manifest = json.loads(manifest_path.read_text())
    assert "license_scan" in manifest
    assert field(manifest["license_scan"], "blocked") is True
    assert field(manifest["license_scan"], "evaluated") is True
    assert field(manifest["license_scan"], "similarity_score") == pytest.approx(
        field(first, "similarity_score"))

    # A subsequent retry resolves the finding.
    code_path.write_text(CLEAN_CODE)
    retry = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(retry, "evaluated") is True
    assert field(retry, "blocked") is False

    # The result is written into license_scan regardless of outcome.
    provenance_writer.write_provenance(COMPONENT_ID, provenance_inputs(retry), repo_root)
    manifest = json.loads(manifest_path.read_text())
    assert "license_scan" in manifest
    assert field(manifest["license_scan"], "blocked") is False
    assert field(manifest["license_scan"], "evaluated") is True

    # Stand-in provenance-tracker: components/capabilities keyed by id.
    first_dict = as_plain_dict(first, LICENSE_FIELDS)
    secret_dict = as_plain_dict(secret_result, SECRET_FIELDS)
    component_entry = {
        "component_id": COMPONENT_ID,
        "ready": False,
        "blocked": True,
        "provenance_hit": False,
        "verification_report": None,
        "license_scan": first_dict,
        "secret_scan": secret_dict,
        "reasons": ["license_scan_blocked"],
    }
    verify_report = {
        "ready": False,
        "overall": "fail",
        "components": {COMPONENT_ID: component_entry},
        "capabilities": {},
    }
    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "provenance_tracker.py").write_text(
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )

    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "retry")

    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    flags = field(packet, "compliance_flags")
    license_flags = field(flags, "license_scan")
    matching = [e for e in license_flags if field(e, "component_id") == COMPONENT_ID]
    assert len(matching) == 1
    assert field(field(matching[0], "result"), "blocked") is True