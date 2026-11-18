# hotdocs-criterion: sha256:f7ba8474a0a5845a8fc7b934f4555f4b0b0d7619a5bf501b0b55dc23b5505e6e
import dataclasses
import hashlib
import io
import json
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

LICENSED_CODE = (
    "def merge_intervals(intervals):\n"
    "    ordered = sorted(intervals, key=lambda pair: pair[0])\n"
    "    merged = []\n"
    "    for start, end in ordered:\n"
    "        if merged and start <= merged[-1][1]:\n"
    "            merged[-1][1] = max(merged[-1][1], end)\n"
    "        else:\n"
    "            merged.append([start, end])\n"
    "    return merged\n"
    "\n"
    "\n"
    "def total_covered(intervals):\n"
    "    return sum(end - start for start, end in merge_intervals(intervals))\n"
)

RETRY_CODE = (
    "def greet_visitor(name_text):\n"
    "    banner_line = 'welcome ' + name_text\n"
    "    return banner_line.upper()\n"
    "\n"
    "\n"
    "def count_vowels(word_value):\n"
    "    vowel_set = 'aeiou'\n"
    "    return len([ch for ch in word_value.lower() if ch in vowel_set])\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(value):
    if isinstance(value, dict):
        return {k: as_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_plain(v) for v in value]
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return as_plain(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return as_plain(dataclasses.asdict(value))
    return value


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component_code(repo_root, text):
    write(repo_root / "gen" / SLUG / (SLUG + ".py"), text)
    write(repo_root / "legacy" / SLUG / (SLUG + ".py"), text)


def cache_manager_source():
    return (
        "import os\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    path = os.environ.get('HOTDOCS_TEST_CACHE_LOG')\n"
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
        "VERIFY_REPORT = " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    path = os.environ.get('HOTDOCS_TEST_TRACKER_LOG')\n"
        "    if path:\n"
        "        with open(path, 'a', encoding='utf-8') as fh:\n"
        "            fh.write('check_readiness\\n')\n"
        "    return VERIFY_REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "components" / SLUG / "component.md",
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
        "A fixture component.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\nFoo merges intervals.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\n\nFoo merges overlapping intervals.\n",
    )
    write_component_code(repo_root, LICENSED_CODE)
    write(
        repo_root / "compliance" / "license-corpus.json",
        json.dumps(
            {
                "corpus_version": 3,
                "block_threshold": 0.70,
                "entries": [
                    {
                        "reference_id": "ref-001",
                        "license_family": "GPL",
                        "risk_tier": "high",
                        "hashes": window_hashes(LICENSED_CODE),
                    }
                ],
            },
            indent=2,
        ),
    )
    write(repo_root / "gen" / "cache-manager" / "cache_manager.py", cache_manager_source())

    def git(*args):
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
        )

    git("init")
    git("add", "-A")
    git("commit", "-m", "fixture")


def secret_scan_result():
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
        "overall": "pass",
        "criteria": [
            {
                "criterion_id": "AC-FOO-001",
                "result": "pass",
                "failure_origin": None,
                "failure_detail": None,
            }
        ],
        "mutation_score": 1.0,
        "mutation_error": None,
        "run_id": "run-1",
        "verification_run_id": "run-1",
    }


def generation_result():
    return {
        "component_id": COMPONENT_ID,
        "files": ["gen/foo/foo.py"],
        "model_call_error": None,
        "refused": None,
        "model": "anthropic:claude-sonnet-5",
        "model_pin": "anthropic:claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "spec_bundle_hash": "sha256:" + "0" * 64,
    }


def provenance_inputs(license_result, attempts):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result(),
        "verification_report": verification_report(),
        "license_scan_result": license_result,
        "secret_scan_result": secret_scan_result(),
        "provenance_hit": False,
        "attempts": attempts,
        "gate_versions": {
            "license_scanner": field(license_result, "gate_version"),
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        },
    }


def read_manifests(repo_root):
    paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    manifests = []
    for path in paths:
        assert path.is_file(), "missing provenance manifest at " + str(path)
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def run_license_cli(repo_root):
    try:
        code = license_scanner.main([COMPONENT_ID, "--repo-root", str(repo_root), "--format", "json"])
    except SystemExit as exc:
        code = exc.code
    return 0 if code is None else code


def test_cs_compliance_001(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    tracker_log = logs / "tracker.log"

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "compliance/license-corpus.json")
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("HOTDOCS_TEST_TRACKER_LOG", str(tracker_log))
    monkeypatch.setenv("HOTDOCS_TEST_CACHE_LOG", str(logs / "cache.log"))

    def fake_urlopen(*args, **kwargs):
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.chdir(repo_root)

    build_fixture(repo_root)

    # When: the pipeline's license scan runs over the licensed-code match.
    first = license_scanner.scan(COMPONENT_ID, repo_root)
    first_plain = as_plain(first)

    # Then: the merge is blocked.
    assert field(first, "evaluated") is True
    assert field(first, "component_id") == COMPONENT_ID
    assert field(first, "similarity_score") >= field(first, "block_threshold")
    assert field(first, "blocked") is True
    matches = field(first, "matches")
    assert len(matches) >= 1
    assert any(field(m, "reference_id") == "ref-001" for m in matches)
    assert run_license_cli(repo_root) == 1
    capsys.readouterr()

    # The blocked result is written into the provenance manifest's license_scan.
    provenance_writer.write_provenance(COMPONENT_ID, provenance_inputs(first_plain, 1), repo_root)
    for manifest in read_manifests(repo_root):
        recorded = manifest["license_scan"]
        assert recorded["blocked"] is True
        assert recorded["evaluated"] is True
        assert recorded["component_id"] == COMPONENT_ID
        assert recorded["similarity_score"] == field(first, "similarity_score")
        assert recorded["gate_version"] == field(first, "gate_version")

    # The provenance-tracker stand-in reports the flagged finding, with
    # "components" and "capabilities" as mappings keyed by id.
    verify_report = {
        "ready": False,
        "blocked": True,
        "overall": "fail",
        "components": {
            COMPONENT_ID: {
                "component_id": COMPONENT_ID,
                "status": "blocked",
                "blocked": True,
                "regenerated": True,
                "provenance_hit": False,
                "verification": verification_report(),
                "verification_report": verification_report(),
                "license_scan": first_plain,
                "secret_scan": secret_scan_result(),
                "block_reasons": ["license_scan"],
            }
        },
        "capabilities": {},
        "blocking": [{"component_id": COMPONENT_ID, "reason": "license_scan"}],
    }
    write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_source(verify_report),
    )

    # A subsequent retry resolves the finding.
    write_component_code(repo_root, RETRY_CODE)
    second = license_scanner.scan(COMPONENT_ID, repo_root)
    second_plain = as_plain(second)
    assert field(second, "evaluated") is True
    assert field(second, "blocked") is False
    assert run_license_cli(repo_root) == 0
    capsys.readouterr()

    # The result is written regardless of outcome: the clean one too.
    provenance_writer.write_provenance(COMPONENT_ID, provenance_inputs(second_plain, 2), repo_root)
    for manifest in read_manifests(repo_root):
        recorded = manifest["license_scan"]
        assert recorded["blocked"] is False
        assert recorded["evaluated"] is True
        assert recorded["component_id"] == COMPONENT_ID

    # The original finding still appears in the review packet.
    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    assert tracker_log.is_file()
    assert "check_readiness" in tracker_log.read_text(encoding="utf-8")

    flags = field(packet, "compliance_flags")
    license_flags = field(flags, "license_scan")
    assert isinstance(license_flags, list)
    flagged = [entry for entry in license_flags if field(entry, "component_id") == COMPONENT_ID]
    assert len(flagged) >= 1, "blocked license finding missing from review packet"
    assert any(field(field(entry, "result"), "blocked") is True for entry in flagged)