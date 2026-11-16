"""CS-COMPLIANCE-001: licensed-code risk never reaches main silently.

Given generated code that matches a known-licensed-code fingerprint above the
similarity threshold, when the pipeline's license scan runs, then the merge is
blocked, the result is written into the provenance manifest's license_scan
field regardless of outcome, and the finding appears in the review packet even
if a subsequent retry resolves it.
"""

import dataclasses
import hashlib
import json
import pprint
import re
import subprocess
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import component_gate_runner
import license_scanner
import provenance_writer
import review_packet_builder
import secret_scanner


COMPONENT_ID = "comp-licfixture"
SLUG = "licfixture"
MODEL = "anthropic:claude-sonnet-5"
RETRY_FEEDBACK = ["R-LICFIX-001"]
REFERENCE_ID = "ref-ringbuf"
SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32
SECRET_GATE_VERSION = "secret_scanner@3.1.0+detect-secrets.1.5.0"


# Generated code that a reference corpus entry fingerprints in full. It holds
# no comments, no string literals and no floor division, so the documented
# comment stripping never changes its token stream.
LICENSED_SOURCE = textwrap.dedent(
    """\
    def interleave_ring_buffer(capacity, values):
        ring = [None] * capacity
        head = 0
        count = 0
        for value in values:
            ring[head] = value
            head = (head + 1) % capacity
            if count < capacity:
                count = count + 1
        ordered = []
        start = (head - count) % capacity
        for offset in range(count):
            ordered.append(ring[(start + offset) % capacity])
        return ordered


    def weighted_reservoir_merge(left, right, weight_left, weight_right):
        merged = []
        left_index = 0
        right_index = 0
        while left_index < len(left) and right_index < len(right):
            left_score = left[left_index] * weight_left
            right_score = right[right_index] * weight_right
            if left_score <= right_score:
                merged.append(left[left_index])
                left_index = left_index + 1
            else:
                merged.append(right[right_index])
                right_index = right_index + 1
        merged.extend(left[left_index:])
        merged.extend(right[right_index:])
        return merged


    def cascade_checksum(blocks, modulus, seed_value):
        accumulator = seed_value
        rolling = 1
        for block in blocks:
            for item in block:
                rolling = (rolling * 31 + item) % modulus
                accumulator = (accumulator + rolling * 7) % modulus
            accumulator = (accumulator ^ rolling) % modulus
        return accumulator, rolling
    """
)

# What the retry generates: shares no 9-token window with the corpus.
CLEAN_SOURCE = textwrap.dedent(
    """\
    def total_of(numbers):
        result = 0
        for n in numbers:
            result = result + n
        return result
    """
)

VERIFICATION_REPORT = {
    "component_id": COMPONENT_ID,
    "overall": "pass",
    "criteria": [],
    "run_id": "run-licfix-1",
    "verification_run_id": "run-licfix-1",
    "mutation_score": 1.0,
}

CLEAN_SECRET_SCAN = {
    "scope": "full",
    "gate_version": SECRET_GATE_VERSION,
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


# ---------------------------------------------------------------------------
# helpers


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if hasattr(value, "to_dict"):
        return plain(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return plain(dataclasses.asdict(value))
    if hasattr(value, "__dict__"):
        return plain(vars(value))
    return value


def normalize(value):
    return json.loads(json.dumps(plain(value)))


def window_hashes(text):
    """The documented window hashing, applied to the fingerprinted source."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for start in range(len(tokens) - 8):
        window = "\x1f".join(tokens[start:start + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# fake dependency modules (flat shape under <repo_root>/gen/<slug>/)

_COMMON = textwrap.dedent(
    '''\
    import json
    import os
    from pathlib import Path


    def _log(entry):
        path = os.environ.get("HOTDOCS_TEST_LOG")
        if path:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\\n")


    def _field(value, name, default=None):
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    '''
)

_PROVENANCE_CHECKER = '''

def current_sealed_key(component_id, repo_root):
    _log({"call": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"call": "current_provenance_key", "component_id": component_id})
    return {
        "component_id": component_id,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "gate_versions": dict(GATE_VERSIONS),
    }


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"call": "check_provenance", "component_id": component_id})
    return {
        "component_id": component_id,
        "hit": False,
        "status": "miss",
        "reason": "no-manifest",
        "verification": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

_SPEC_BUNDLE_ASSEMBLER = '''

def assemble(component_id, repo_root=None, mode="cold"):
    _log({"call": "assemble", "component_id": component_id, "mode": mode})
    return {"component_id": component_id, "mode": mode, "files": {}}
'''

_GENERATOR = '''

def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    component_id = _field(bundle, "component_id") or os.environ["HOTDOCS_TEST_COMPONENT"]
    slug = component_id[len("comp-"):]
    control = Path(os.environ["HOTDOCS_TEST_CONTROL"])
    source_name = "clean.py.txt" if retry_feedback else "licensed.py.txt"
    text = (control / source_name).read_text(encoding="utf-8")
    relative = "gen/" + slug + "/" + slug.replace("-", "_") + ".py"
    target = Path(repo_root) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    feedback = list(retry_feedback) if retry_feedback is not None else None
    _log({
        "call": "generate",
        "component_id": component_id,
        "model": model,
        "retry_feedback": feedback,
        "source": source_name,
    })
    return {
        "component_id": component_id,
        "model": model,
        "model_pin": model,
        "prompt_version": "v1",
        "pipeline_version": "v1",
        "retry_feedback": feedback,
        "files": {relative: text},
        "model_call_error": None,
        "refused": None,
    }
'''

_VERIFIER_ORCHESTRATOR = '''

def verify(component_id, repo_root, judge=None, test_author=None):
    _log({"call": "verify", "component_id": component_id})
    return dict(VERIFICATION_REPORT)
'''

_TEST_AUTHOR = '''

def author_test(criterion_bundle, model, seed=0, repo_root=None, llm_backend=None):
    _log({"call": "author_test", "model": model})
    return {"model_call_error": None, "file": None}
'''

_LLM_ENDPOINT = '''

def complete(prompt, model, backend=None):
    _log({"call": "complete", "model": model})
    return "pass"
'''

_CACHE_MANAGER = '''

class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,
                 gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


class Miss:
    payload = None


def get(cache_key, repo_root=None):
    _log({"call": "cache_get", "gate_version": _field(cache_key, "gate_version")})
    return Miss()


def put(cache_key, cached_result, repo_root=None):
    _log({"call": "cache_put", "gate_type": _field(cached_result, "gate_type")})
    return None
'''

_SECRET_SCANNER = '''
from dataclasses import asdict, dataclass
from dataclasses import field as dc_field


class AllowlistInvalidError(Exception):
    pass


@dataclass
class SecretScanResult:
    scope: str = "full"
    gate_version: str = SECRET_GATE_VERSION
    flagged: bool = False
    matches: list = dc_field(default_factory=list)
    allowed: list = dc_field(default_factory=list)
    unused_allowlist_entries: list = dc_field(default_factory=list)
    notified: bool = False
    notification_delivery_error: object = None
    cache_hit: bool = False

    def to_dict(self):
        return asdict(self)


def scan(repo_root):
    _log({"call": "secret_scan"})
    return SecretScanResult()


def scan_files(paths, repo_root=None):
    _log({"call": "secret_scan_files"})
    return SecretScanResult(scope="precommit")


def gate_version(repo_root):
    return SECRET_GATE_VERSION


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

_PROVENANCE_TRACKER_HEAD = '''

def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):]
    directory = Path(repo_root) / ".hotdocs" / "attempts" / slug
    directory.mkdir(parents=True, exist_ok=True)
    number = len(list(directory.iterdir())) + 1
    record = {
        "component_id": component_id,
        "attempt": number,
        "spec_bundle_hash": spec_bundle_hash,
        "retry_feedback": _field(generation_result, "retry_feedback"),
        "verification_overall": (
            _field(verification_report, "overall")
            if verification_report is not None else None
        ),
    }
    (directory / ("attempt-%03d.json" % number)).write_text(
        json.dumps(record), encoding="utf-8"
    )
    _log({"call": "write_attempt_record", "component_id": component_id, "attempt": number})
    return record


def last_requirement_failures(component_id, repo_root):
    return []


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({"call": "check_readiness", "changed_ids": changed_ids})
    return '''


def _fake(repo, slug, body, prelude=""):
    module = slug.replace("-", "_")
    _write(repo / "gen" / slug / f"{module}.py", _COMMON + prelude + body)


def _write_spec_fixture(repo):
    base = repo / "specs" / "components" / SLUG
    _write(
        base / "component.md",
        textwrap.dedent(
            f"""\
            ---
            id: {COMPONENT_ID}
            title: License Fixture Component
            status: draft
            owners: [pipeline-team]
            depends_on: []
            ---

            # License Fixture Component

            Synthetic component whose generated code the test controls.
            """
        ),
    )
    _write(base / "requirements" / "R-LICFIX-001.md", "Returns the requested values.\n")
    _write(
        base / "acceptance" / "AC-LICFIX-001.md",
        "Covers: R-LICFIX-001\n\nThe requested values are returned.\n",
    )
    _write(base / "interface" / "library.md", "One function.\n")
    _write(base / "constraints.md", "None.\n")


def _git(repo, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# the test


def test_cs_compliance_001_licensed_match_blocks_records_and_surfaces(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    control = tmp_path / "control"
    repo.mkdir()
    control.mkdir()
    log_path = control / "calls.jsonl"

    _write(control / "licensed.py.txt", LICENSED_SOURCE)
    _write(control / "clean.py.txt", CLEAN_SOURCE)

    # Reference corpus fingerprinting the licensed code, outside repo_root.
    hashes = window_hashes(LICENSED_SOURCE)
    assert len(hashes) > 100
    corpus_path = control / "license-corpus.json"
    _write(
        corpus_path,
        json.dumps(
            {
                "corpus_version": 3,
                "block_threshold": 0.70,
                "entries": [
                    {
                        "reference_id": REFERENCE_ID,
                        "license_family": "GPL",
                        "risk_tier": "high",
                        "hashes": hashes,
                    }
                ],
            }
        ),
    )

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))
    monkeypatch.setenv("HOTDOCS_TEST_CONTROL", str(control))
    monkeypatch.setenv("HOTDOCS_TEST_COMPONENT", COMPONENT_ID)

    def _no_network(*args, **kwargs):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"call": "urlopen"}) + "\n")
        raise urllib.error.URLError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)

    license_gate_version = license_scanner.gate_version(repo)
    assert license_gate_version.startswith("license_scanner@4.0.3+")

    gate_versions = {
        "license_scanner": license_gate_version,
        "secret_scanner": SECRET_GATE_VERSION,
    }

    # What provenance-tracker's readiness check reports for this PR: the
    # license finding raised during the pipeline run that blocked the merge.
    blocked_license_literal = {
        "component_id": COMPONENT_ID,
        "gate_version": license_gate_version,
        "evaluated": True,
        "reason": None,
        "similarity_score": 1.0,
        "block_threshold": 0.7,
        "blocked": True,
        "matches": [
            {
                "reference_id": REFERENCE_ID,
                "license_family": "GPL",
                "risk_tier": "high",
                "score": 1.0,
            }
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    verify_report = {
        "ready": False,
        "changed_ids": [COMPONENT_ID],
        "blast_radius": [COMPONENT_ID],
        "regenerated_components": [COMPONENT_ID],
        "components": {
            COMPONENT_ID: {
                "component_id": COMPONENT_ID,
                "ready": False,
                "provenance_hit": False,
                "blocked": True,
                "block_reason": "license_scan_blocked",
                "verification": dict(VERIFICATION_REPORT),
                "license_scan": blocked_license_literal,
                "secret_scan": dict(CLEAN_SECRET_SCAN),
                "attempts": 2,
            }
        },
        "capabilities": {},
        "blocking": [{"component_id": COMPONENT_ID, "reason": "license_scan_blocked"}],
    }

    # Fixture repo: the component spec plus stand-ins for every dependency
    # the gate runner reaches, except the real license-scanner and
    # provenance-writer, which are the subjects here.
    _write_spec_fixture(repo)
    _fake(
        repo,
        "provenance-checker",
        _PROVENANCE_CHECKER,
        prelude=(
            "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH) + "\n"
            "GATE_VERSIONS = " + repr(gate_versions) + "\n"
        ),
    )
    _fake(repo, "spec-bundle-assembler", _SPEC_BUNDLE_ASSEMBLER)
    _fake(repo, "generator", _GENERATOR)
    _fake(
        repo,
        "verifier-orchestrator",
        _VERIFIER_ORCHESTRATOR,
        prelude="VERIFICATION_REPORT = " + repr(VERIFICATION_REPORT) + "\n",
    )
    _fake(repo, "test-author", _TEST_AUTHOR)
    _fake(repo, "llm-endpoint", _LLM_ENDPOINT)
    _fake(repo, "cache-manager", _CACHE_MANAGER)
    _fake(
        repo,
        "secret-scanner",
        _SECRET_SCANNER,
        prelude="SECRET_GATE_VERSION = " + repr(SECRET_GATE_VERSION) + "\n",
    )
    _fake(
        repo,
        "provenance-tracker",
        _PROVENANCE_TRACKER_HEAD + pprint.pformat(verify_report, width=100) + "\n",
    )

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")

    manifest_paths = [
        repo / "gen" / SLUG / ".provenance.json",
        repo / "verification" / SLUG / ".provenance.json",
    ]

    # ---- first run: generated code matches the licensed fingerprint ----
    first = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo, MODEL, seed=0, llm_backend=None, retry_feedback=None
    )
    assert field(first, "component_id") == COMPONENT_ID
    assert field(first, "provenance_hit") is False

    first_license = field(first, "license_scan")
    assert field(first_license, "evaluated") is True
    assert field(first_license, "reason") is None
    assert field(first_license, "gate_version") == license_gate_version
    threshold = field(first_license, "block_threshold")
    assert threshold == pytest.approx(0.70)
    assert field(first_license, "similarity_score") > threshold
    # The merge is blocked by the license gate.
    assert field(first_license, "blocked") is True
    first_matches = field(first_license, "matches")
    assert any(field(m, "reference_id") == REFERENCE_ID for m in first_matches)

    # The blocked result is written into the manifest's license_scan field.
    for path in manifest_paths:
        assert path.is_file(), f"provenance manifest missing at {path}"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert "license_scan" in manifest
        assert normalize(manifest["license_scan"]) == normalize(first_license)
        assert manifest["license_scan"]["blocked"] is True

    # ---- retry: regenerated code no longer matches ----
    second = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo, MODEL, seed=0, llm_backend=None,
        retry_feedback=list(RETRY_FEEDBACK),
    )
    second_license = field(second, "license_scan")
    assert field(second_license, "evaluated") is True
    assert field(second_license, "blocked") is False

    # Written into the manifest regardless of outcome: the clean result too.
    for path in manifest_paths:
        assert path.is_file(), f"provenance manifest missing at {path}"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert normalize(manifest["license_scan"]) == normalize(second_license)
        assert manifest["license_scan"]["blocked"] is False

    calls = _read_log(log_path)
    generate_calls = [c for c in calls if c["call"] == "generate"]
    assert [c["retry_feedback"] for c in generate_calls] == [None, RETRY_FEEDBACK]
    assert len([c for c in calls if c["call"] == "write_attempt_record"]) == 2

    # ---- the finding still appears in the review packet ----
    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo)
    compliance_flags = field(packet, "compliance_flags")
    license_flags = field(compliance_flags, "license_scan")
    entries = [e for e in license_flags if field(e, "component_id") == COMPONENT_ID]
    assert entries, (
        "the license finding was resolved by a retry but must still appear in "
        f"the review packet; got {normalize(license_flags)!r}"
    )
    flagged_result = field(entries[0], "result")
    assert field(flagged_result, "blocked") is True
    assert any(
        field(m, "reference_id") == REFERENCE_ID
        for m in field(flagged_result, "matches")
    )