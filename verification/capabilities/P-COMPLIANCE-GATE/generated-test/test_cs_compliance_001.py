# hotdocs-criterion: sha256:84f0c3d8811b8fdb871a9f614d596635f190a1c5d0c801e21dea877e2495ed7e
"""CS-COMPLIANCE-001 (P-COMPLIANCE-GATE).

Given generated code that matches a known-licensed-code fingerprint above the
similarity threshold, and a stand-in provenance-tracker whose check_readiness
returns a VerifyReport whose "components" and "capabilities" are mappings
keyed by id, when the pipeline's license scan runs, then the merge is blocked,
the result is written into the provenance manifest's license_scan field
regardless of outcome, and the finding appears in the review packet even if a
subsequent retry resolves it.
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


COMPONENT_ID = "comp-licfoo"
SLUG = "licfoo"
REFERENCE_ID = "ref-gpl-001"

TRACKER_LOG_ENV = "HOTDOCS_TEST_TRACKER_LOG"
CACHE_LOG_ENV = "HOTDOCS_TEST_CACHE_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_dict(value):
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return dict(vars(value))


def jsonable(value):
    return json.loads(json.dumps(as_dict(value)))


# Generated code that is (by construction of the corpus below) a verbatim copy
# of a known-licensed reference. No comments, so stripping changes nothing.
LICENSED_CODE = (
    "import math\n"
    "\n"
    "\n"
    "def weighted_median(values, weights):\n"
    "    pairs = sorted(zip(values, weights))\n"
    "    total = sum(weight for _, weight in pairs)\n"
    "    running = 0\n"
    "    for value, weight in pairs:\n"
    "        running = running + weight\n"
    "        if running * 2 >= total:\n"
    "            return value\n"
    "    return None\n"
    "\n"
    "\n"
    "def geometric_mean(numbers):\n"
    "    if not numbers:\n"
    "        return 0\n"
    "    log_sum = 0\n"
    "    for number in numbers:\n"
    "        log_sum = log_sum + math.log(number)\n"
    "    return math.exp(log_sum / len(numbers))\n"
    "\n"
    "\n"
    "def harmonic_mean(numbers):\n"
    "    if not numbers:\n"
    "        return 0\n"
    "    reciprocal_total = 0\n"
    "    for number in numbers:\n"
    "        reciprocal_total = reciprocal_total + 1 / number\n"
    "    return len(numbers) / reciprocal_total\n"
    "\n"
    "\n"
    "class RollingWindow:\n"
    "    def __init__(self, capacity):\n"
    "        self.capacity = capacity\n"
    "        self.items = []\n"
    "\n"
    "    def push(self, item):\n"
    "        self.items.append(item)\n"
    "        while len(self.items) > self.capacity:\n"
    "            self.items.pop(0)\n"
    "\n"
    "    def average(self):\n"
    "        if not self.items:\n"
    "            return 0\n"
    "        return sum(self.items) / len(self.items)\n"
)

# The retried candidate: entirely different code, sharing no 9-token window.
RESOLVED_CODE = (
    "def greet(person_name):\n"
    "    greeting_word = 'hello'\n"
    "    return greeting_word + ' ' + person_name\n"
    "\n"
    "\n"
    "def count_vowels(sentence):\n"
    "    vowel_letters = 'aeiou'\n"
    "    tally = 0\n"
    "    for letter in sentence.lower():\n"
    "        if letter in vowel_letters:\n"
    "            tally = tally + 1\n"
    "    return tally\n"
    "\n"
    "\n"
    "def reverse_words(phrase):\n"
    "    pieces = phrase.split()\n"
    "    pieces.reverse()\n"
    "    return ' '.join(pieces)\n"
)


def window_hashes(text):
    stripped = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    stripped = re.sub(r'""".*?"""', " ", stripped, flags=re.S)
    stripped = re.sub(r"'''.*?'''", " ", stripped, flags=re.S)
    stripped = re.sub(r"//[^\n]*", " ", stripped)
    stripped = re.sub(r"#[^\n]*", " ", stripped)
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", stripped)]
    hashes = []
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.append(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(set(hashes))


CACHE_MANAGER_SOURCE = (
    "import os\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    path = os.environ.get(" + repr(CACHE_LOG_ENV) + ")\n"
    "    if path:\n"
    "        with open(path, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "class CacheKey:\n"
    "    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None, gate_version=None, model_pin=None):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_inputs_hash = gate_inputs_hash\n"
    "        self.gate_version = gate_version\n"
    "        self.model_pin = model_pin\n"
    "\n"
    "\n"
    "class CachedResult:\n"
    "    def __init__(self, gate_type=None, payload=None, stored_at=None):\n"
    "        self.gate_type = gate_type\n"
    "        self.payload = payload\n"
    "        self.stored_at = stored_at\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __init__(self, reason='absent'):\n"
    "        self.reason = reason\n"
    "        self.payload = None\n"
    "\n"
    "\n"
    "def get(cache_key, repo_root=None):\n"
    "    _log('get')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, cached_result, repo_root=None):\n"
    "    _log('put')\n"
    "    return None\n"
)


def tracker_source(verify_report):
    return (
        "import os\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    path = os.environ.get(" + repr(TRACKER_LOG_ENV) + ")\n"
        "    if path:\n"
        "        with open(path, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root), check=True, capture_output=True,
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "components" / SLUG / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Lic Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Lic Foo\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "requirements" / "R-LICFOO-001.md",
        "# R-LICFOO-001\n\nIt computes means.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "acceptance" / "AC-LICFOO-001.md",
        "# AC-LICFOO-001\n\nCovers: R-LICFOO-001\n",
    )
    write(repo_root / "gen" / SLUG / "licfoo.py", LICENSED_CODE)
    write(repo_root / "gen" / "cache-manager" / "cache_manager.py", CACHE_MANAGER_SOURCE)


def secret_clean():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def verification_report():
    return {
        "component_id": COMPONENT_ID,
        "run_id": "run-licfoo-1",
        "overall": "pass",
        "criteria": [
            {"criterion_id": "AC-LICFOO-001", "kind": "generated-test",
             "covers": ["R-LICFOO-001"], "result": "pass", "failure_detail": None},
        ],
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
    }


def generation_result(code):
    return {
        "component_id": COMPONENT_ID,
        "files": {"licfoo.py": code},
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "mode": "single",
        "generator_version": "generator@3.0.0+v11",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
        "model_call_error": None,
        "refused": False,
    }


def run_license_cli(repo_root):
    try:
        code = license_scanner.main([COMPONENT_ID, "--repo-root", str(repo_root), "--format", "json"])
    except SystemExit as exc:
        code = exc.code
    return 0 if code is None else code


def test_cs_compliance_001_licensed_match_blocks_records_and_surfaces(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    corpus_path = tmp_path / "corpus" / "corpus.json"
    write(corpus_path, json.dumps({
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {"reference_id": REFERENCE_ID, "license_family": "GPL", "risk_tier": "high",
             "hashes": window_hashes(LICENSED_CODE)},
        ],
    }))

    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv(CACHE_LOG_ENV, str(logs / "cache.log"))
    monkeypatch.setenv(TRACKER_LOG_ENV, str(logs / "tracker.log"))

    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "fixture")

    # --- The license scan runs on the licensed-looking candidate. ---
    flagged = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(flagged, "evaluated") is True
    assert field(flagged, "component_id") == COMPONENT_ID
    score = field(flagged, "similarity_score")
    threshold = field(flagged, "block_threshold")
    assert threshold == 0.70
    assert score > threshold
    # Then the merge is blocked.
    assert field(flagged, "blocked") is True
    match_ids = [field(m, "reference_id") for m in field(flagged, "matches")]
    assert REFERENCE_ID in match_ids

    assert run_license_cli(repo_root) == 1
    capsys.readouterr()

    # --- The result is written into the manifest's license_scan field,
    # even though the outcome is a block. ---
    inputs = {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result(LICENSED_CODE),
        "verification_report": verification_report(),
        "license_scan_result": flagged,
        "secret_scan_result": secret_clean(),
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [
            {"number": 1, "outcome": "passed", "retry_feedback": [],
             "error_category": None, "failed_requirements": [],
             "transcript_sha256": None},
        ],
        "gate_versions": {"license_scanner": field(flagged, "gate_version")},
    }
    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    flagged_json = jsonable(flagged)
    for manifest_path in (
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ):
        assert manifest_path.is_file(), manifest_path
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        recorded = manifest["license_scan"]
        assert recorded["blocked"] is True
        assert recorded["component_id"] == COMPONENT_ID
        assert recorded["evaluated"] is True
        assert recorded["similarity_score"] == flagged_json["similarity_score"]
        assert recorded["block_threshold"] == flagged_json["block_threshold"]
        assert recorded["gate_version"] == flagged_json["gate_version"]
        assert [m["reference_id"] for m in recorded["matches"]] == [
            m["reference_id"] for m in flagged_json["matches"]
        ]

    # --- A subsequent retry resolves the finding. ---
    write(repo_root / "gen" / SLUG / "licfoo.py", RESOLVED_CODE)
    resolved = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(resolved, "evaluated") is True
    assert field(resolved, "blocked") is False
    assert field(resolved, "similarity_score") < field(resolved, "block_threshold")

    # --- The finding still appears in the review packet. ---
    verify_report = {
        "ready": False,
        "blocked": True,
        "changed_ids": [COMPONENT_ID],
        "components": {
            COMPONENT_ID: {
                "component_id": COMPONENT_ID,
                "ready": False,
                "sealed": False,
                "regenerated": True,
                "provenance_hit": False,
                "blockers": ["license_scan"],
                "verification_report": verification_report(),
                "verification": verification_report(),
                "license_scan": flagged_json,
                "secret_scan": secret_clean(),
            },
        },
        "capabilities": {},
    }
    write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_source(verify_report),
    )

    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)

    tracker_log = logs / "tracker.log"
    assert tracker_log.is_file()
    assert "check_readiness" in tracker_log.read_text(encoding="utf-8").splitlines()

    flags = field(packet, "compliance_flags")
    license_entries = field(flags, "license_scan")
    ours = [e for e in license_entries if field(e, "component_id") == COMPONENT_ID]
    assert len(ours) == 1, license_entries
    surfaced = field(ours[0], "result")
    assert field(surfaced, "blocked") is True
    assert REFERENCE_ID in [field(m, "reference_id") for m in field(surfaced, "matches")]