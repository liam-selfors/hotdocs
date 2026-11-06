import json
import textwrap
from pathlib import Path

import pytest

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FIXTURE_COMPONENT_ID = "comp-license-fixture"
FIXTURE_SLUG = "license-fixture"

CACHED_PAYLOAD = {
    "component_id": FIXTURE_COMPONENT_ID,
    "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
    "evaluated": True,
    "reason": None,
    "similarity_score": 0.55,
    "block_threshold": 0.70,
    "blocked": False,
    "matches": [
        {
            "reference_id": "ref-123",
            "license_family": "gpl-3.0",
            "risk_tier": "high",
            "score": 0.55,
        }
    ],
    "notified": True,
    "notification_delivery_error": None,
    "cache_hit": True,
}

FAKE_CACHE_MANAGER_SOURCE = textwrap.dedent("""
    import dataclasses
    import json
    from pathlib import Path

    @dataclasses.dataclass
    class CacheKey:
        spec_bundle_hash: str
        gate_inputs_hash: str
        gate_version: str
        model_pin: str

    @dataclasses.dataclass
    class CachedResult:
        gate_type: str
        payload: dict
        stored_at: str

    class Miss:
        pass

    _CACHED_PAYLOAD = __CACHED_PAYLOAD_REPR__

    def _log(event):
        log_path = Path(__file__).parent / "invocations.log"
        with open(log_path, "a") as f:
            f.write(json.dumps({"event": event}) + "\\n")

    def get(cache_key, *, repo_root=None):
        _log("get")
        return CachedResult(
            gate_type="license_scanner",
            payload=dict(_CACHED_PAYLOAD),
            stored_at="2026-01-01T00:00:00Z",
        )

    def put(cache_key, result, *, repo_root=None):
        _log("put")
""").replace("__CACHED_PAYLOAD_REPR__", repr(CACHED_PAYLOAD))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_fixture_component(repo_root: Path) -> None:
    component_dir = repo_root / "specs" / "components" / FIXTURE_SLUG
    _write(
        component_dir / "component.md",
        textwrap.dedent(f"""\
            ---
            id: {FIXTURE_COMPONENT_ID}
            title: License Fixture Component
            status: draft
            owners: [lselfors@gmail.com]
            sealed: true
            source_path: fake-source/{FIXTURE_SLUG}
            ---

            # License Fixture Component

            Synthetic sealed fixture, present only to give AC-LICENSE-004's
            test a minimal valid spec bundle to scan.
            """),
    )
    _write(
        component_dir / "requirements" / "R-FIXTURE-001.md",
        textwrap.dedent("""\
            # R-FIXTURE-001

            **R-FIXTURE-001** — Fixture requirement, present only so this
            synthetic component has a minimal valid spec bundle.
            """),
    )
    _write(
        component_dir / "acceptance" / "AC-FIXTURE-001.md",
        textwrap.dedent("""\
            Covers: R-FIXTURE-001

            # AC-FIXTURE-001

            ```gherkin
            Given the fixture component exists
            When nothing is evaluated
            Then this file only exists to satisfy spec-bundle structure
            ```
            """),
    )


def _write_fake_cache_manager(repo_root: Path) -> Path:
    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True, exist_ok=True)
    (cache_manager_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)
    return cache_manager_dir / "invocations.log"


def test_cache_hit_returns_cached_result_without_rescan(tmp_path, monkeypatch):
    # Unset: a fresh scan here would deterministically yield evaluated=False
    # (reason "no-reference-corpus"), the opposite of the cached payload's
    # evaluated=True -- so an evaluated=True result below can only have come
    # from the cache, never from an actual rescan.
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture_component(repo_root)
    invocation_log = _write_fake_cache_manager(repo_root)

    result = license_scanner.scan(FIXTURE_COMPONENT_ID, repo_root)

    assert _get(result, "component_id") == FIXTURE_COMPONENT_ID
    assert _get(result, "evaluated") is True
    assert _get(result, "reason") is None
    assert _get(result, "similarity_score") == 0.55
    assert _get(result, "block_threshold") == 0.70
    assert _get(result, "blocked") is False
    assert _get(result, "gate_version") == "license_scanner@4.0.3+9f2c41ab07de"

    matches = _get(result, "matches")
    assert len(matches) == 1
    assert _get(matches[0], "reference_id") == "ref-123"
    assert _get(matches[0], "risk_tier") == "high"

    assert invocation_log.exists(), "cache-manager fake's get() was never invoked"
    events = [
        json.loads(line)["event"]
        for line in invocation_log.read_text().splitlines()
        if line.strip()
    ]
    assert "get" in events
    assert "put" not in events