# hotdocs-criterion: sha256:15bdea19b199bfa72d1ed81789f70aba73eb78c06c0769bdc107371cdd30eaf2
import component_gate_runner
import license_scanner
import provenance_writer
import review_packet_builder
import secret_scanner

import dataclasses
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


COMPONENT_ID = "comp-foo"
SLUG = "foo"

LICENSED_CODE = (
    "def accumulate_totals(records, threshold):\n"
    "    running = 0\n"
    "    kept = []\n"
    "    for record in records:\n"
    "        value = record.amount * 3 + record.offset\n"
    "        if value > threshold:\n"
    "            kept.append(value)\n"
    "            running = running + value\n"
    "    return running, kept\n"
)

RETRY_CODE = (
    "class Banner:\n"
    "    def __init__(self, label, size):\n"
    "        self.label = label\n"
    "        self.size = size\n"
    "\n"
    "    def measure(self):\n"
    "        return len(self.label) + self.size * 7\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if isinstance(value, dict):
        return json.loads(json.dumps(value))
    if hasattr(value, "to_dict"):
        return json.loads(json.dumps(value.to_dict()))
    if dataclasses.is_dataclass(value):
        return json.loads(json.dumps(dataclasses.asdict(value)))
    return json.loads(json.dumps(dict(vars(value))))


def window_hashes(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        joined = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root), check=True, capture_output=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "components" / SLUG / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n\n# Foo\n\nA fixture component.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\nFoo accumulates totals.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\nCovers: R-FOO-001\n\nGiven records, when accumulated, then totals are kept.\n",
    )
    write(repo_root / "gen" / SLUG / "foo.py", LICENSED_CODE)
    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "fixture")


def generation_result(code):
    return {
        "files": {"foo.py": code},
        "spec_bundle_hash": "sha256:" + "0" * 64,
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


def verification_report():
    return {
        "component_id": COMPONENT_ID,
        "overall": "pass",
        "run_id": "run-1",
        "criteria": [
            {"criterion_id": "AC-FOO-001", "result": "pass", "failure_detail": None},
        ],
        "mutation_score": 1.0,
        "mutation_error": None,
        "assets": [],
    }


def provenance_inputs(code, license_result, secret_result, attempts, history, repo_root):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result(code),
        "verification_report": verification_report(),
        "license_scan_result": license_result,
        "secret_scan_result": secret_result,
        "provenance_hit": False,
        "attempts": attempts,
        "attempt_history": history,
        "gate_versions": {
            "license_scanner": license_scanner.gate_version(repo_root),
            "secret_scanner": secret_scanner.gate_version(repo_root),
        },
    }


def history_entry(number, outcome):
    return {
        "number": number,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": None,
        "failed_requirements": [],
        "transcript_sha256": None,
    }


def read_manifests(repo_root):
    manifests = []
    for path in (
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ):
        assert path.is_file(), "missing provenance manifest at " + str(path)
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def test_cs_compliance_001(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    corpus_path = corpus_dir / "corpus.json"
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": sorted(window_hashes(LICENSED_CODE)),
            }
        ],
    }
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    log_path = tmp_path / "tracker.log"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("CS_COMPLIANCE_001_LOG", str(log_path))

    # The pipeline's license scan over code matching the licensed fingerprint.
    blocked_result = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(blocked_result, "evaluated") is True
    assert field(blocked_result, "blocked") is True, "merge must be blocked"
    assert field(blocked_result, "similarity_score") >= field(blocked_result, "block_threshold")
    matches = field(blocked_result, "matches")
    assert any(field(m, "reference_id") == "ref-001" for m in matches)
    blocked_plain = to_plain(blocked_result)

    secret_result = secret_scanner.scan(repo_root)
    secret_plain = to_plain(secret_result)

    provenance_writer.write_provenance(
        COMPONENT_ID,
        provenance_inputs(
            LICENSED_CODE, blocked_result, secret_result, 1,
            [history_entry(1, "passed")], repo_root,
        ),
        repo_root,
    )
    for manifest in read_manifests(repo_root):
        recorded = manifest["license_scan"]
        assert recorded["blocked"] is True
        assert recorded["evaluated"] is True
        assert recorded["similarity_score"] == blocked_plain["similarity_score"]
        assert recorded["gate_version"] == blocked_plain["gate_version"]

    # A subsequent retry replaces the code with something that no longer matches.
    write(repo_root / "gen" / SLUG / "foo.py", RETRY_CODE)
    clean_result = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(clean_result, "evaluated") is True
    assert field(clean_result, "blocked") is False
    clean_plain = to_plain(clean_result)

    provenance_writer.write_provenance(
        COMPONENT_ID,
        provenance_inputs(
            RETRY_CODE, clean_result, secret_result, 2,
            [history_entry(1, "passed"), history_entry(2, "passed")], repo_root,
        ),
        repo_root,
    )
    # Written regardless of outcome: the clean result is recorded too.
    for manifest in read_manifests(repo_root):
        recorded = manifest["license_scan"]
        assert recorded["blocked"] is False
        assert recorded["evaluated"] is True
        assert recorded["similarity_score"] == clean_plain["similarity_score"]

    # Stand-in provenance-tracker reporting the finding recorded for this PR;
    # "components" and "capabilities" are mappings keyed by id.
    report = {
        "ready": False,
        "merge_blocked": True,
        "blocking": [{"component_id": COMPONENT_ID, "reason": "license_scan"}],
        "components": {
            COMPONENT_ID: {
                "component_id": COMPONENT_ID,
                "ready": False,
                "provenance_hit": False,
                "verification_report": verification_report(),
                "license_scan": blocked_plain,
                "secret_scan": secret_plain,
                "blocking_reasons": ["license_scan"],
            }
        },
        "capabilities": {},
    }
    stand_in = (
        "import os\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(os.environ[" + repr("CS_COMPLIANCE_001_LOG") + "], " + repr("a") + ") as handle:\n"
        "        handle.write(" + repr("check_readiness\n") + ")\n"
        "    return REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", stand_in)

    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)

    assert log_path.is_file() and "check_readiness" in log_path.read_text(encoding="utf-8")

    flags = field(packet, "compliance_flags")
    license_flags = field(flags, "license_scan")
    entries = [e for e in license_flags if field(e, "component_id") == COMPONENT_ID]
    assert entries, "license finding must appear in the review packet"
    flagged = field(entries[0], "result")
    assert field(flagged, "blocked") is True
    assert field(flagged, "similarity_score") == blocked_plain["similarity_score"]