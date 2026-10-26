"""One test per AC-GEN-* criterion in
specs/components/generator/acceptance/.
"""

import json

from conftest import FakeBundle, MockBackend
from llm_endpoint import BackendResult
import generator
from generator import GATE_VERSION, PROMPT_VERSION, generate
import cache_manager


def test_ac_gen_001_cold_prompt_contains_exactly_cold_fields(repo_root):
    backend = MockBackend([BackendResult(text="-----BEGIN FILE: foo.py-----\nx = 1\n-----END FILE-----")])
    bundle = FakeBundle()
    generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "FAKE SPEC TEXT" in sent_prompt
    assert "FAKE INTERFACE TEXT" in sent_prompt
    assert "FAKE CONSTRAINTS TEXT" in sent_prompt
    assert "FAKE GLOSSARY TEXT" in sent_prompt
    assert "HINT_CODE" not in sent_prompt
    assert "RETRY_FEEDBACK" not in sent_prompt


def test_ac_gen_002_hint_code_is_a_distinct_section(repo_root):
    backend = MockBackend([BackendResult(text="-----BEGIN FILE: foo.py-----\nx = 1\n-----END FILE-----")])
    bundle = FakeBundle(hint_code={"foo.py": "x = 0"})
    generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "HINT_CODE:" in sent_prompt
    assert json.dumps({"foo.py": "x = 0"}) in sent_prompt


def test_ac_gen_003_prompt_version_matches_frozen_template(repo_root):
    backend = MockBackend([BackendResult(text="")])
    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.prompt_version == PROMPT_VERSION == "v1"


def test_ac_gen_004_model_identifier_passed_through_unchanged(repo_root):
    backend_a = MockBackend([BackendResult(text="")])
    backend_b = MockBackend([BackendResult(text="")])
    generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend_a)
    generate(FakeBundle(spec_bundle_hash="sha256:other"), "claude-opus-5", repo_root=repo_root, llm_backend=backend_b)
    assert backend_a.calls[0][1] == "claude-sonnet-5"
    assert backend_b.calls[0][1] == "claude-opus-5"


def test_ac_gen_005_cache_hit_skips_the_model(repo_root):
    bundle = FakeBundle()
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=generator._gate_inputs_hash(None),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    cached_payload = {
        "component_id": "comp-foo", "model": "claude-sonnet-5", "prompt_version": "v1",
        "cache_hit": False, "files": {"foo.py": "x = 1"}, "model_call_error": None,
        "refused": None, "retry_feedback": None,
    }
    cache_manager.put(
        cache_key,
        cache_manager.CachedResult(gate_type="generator", payload=cached_payload, stored_at=cache_manager.now_iso()),
        repo_root=repo_root,
    )

    backend = MockBackend([])  # would IndexError if ever called
    result = generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.cache_hit is True
    assert result.files == {"foo.py": "x = 1"}
    assert backend.calls == []


def test_ac_gen_006_successful_call_is_cached(repo_root):
    backend = MockBackend([BackendResult(text="-----BEGIN FILE: foo.py-----\nx = 1\n-----END FILE-----")])
    bundle = FakeBundle()
    generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=generator._gate_inputs_hash(None),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    stored = cache_manager.get(cache_key, repo_root=repo_root)
    assert isinstance(stored, cache_manager.CachedResult)
    assert stored.payload["files"] == {"foo.py": "x = 1"}


def test_ac_gen_008_model_call_error_surfaces_cleanly(repo_root):
    backend = MockBackend([BackendResult(text=None, error_category="network", error_message="connection reset")])
    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.model_call_error == {"category": "network", "message": "connection reset"}
    assert result.files == {}
    assert result.cache_hit is False


def test_ac_gen_009_sealed_and_override_refuse_before_any_call(repo_root):
    sealed_dir = repo_root / "specs" / "components" / "sealed-thing"
    sealed_dir.mkdir(parents=True)
    (sealed_dir / "component.md").write_text(
        "---\nid: comp-sealed-thing\nsealed: true\nsource_path: pipeline/sealed-thing/\n---\n\n# Sealed\n"
    )
    override_dir = repo_root / "specs" / "components" / "overridden-thing"
    override_dir.mkdir(parents=True)
    (override_dir / "component.md").write_text(
        "---\nid: comp-overridden-thing\nsealed: false\n---\n\n# Overridden\n"
    )
    (repo_root / "gen" / "overridden-thing").mkdir(parents=True)
    (repo_root / "gen" / "overridden-thing" / ".overrides.json").write_text(
        json.dumps({"files": [{"path": "hot.py", "rationale": "hand-tuned", "owner": "alice"}]})
    )

    backend = MockBackend([])  # would IndexError if ever called
    result_sealed = generate(
        FakeBundle(component_id="comp-sealed-thing"), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend,
    )
    result_override = generate(
        FakeBundle(component_id="comp-overridden-thing"), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend,
    )

    assert result_sealed.refused == "sealed-component"
    assert result_override.refused == "pinned-override"
    for r in (result_sealed, result_override):
        assert r.files == {}
        assert r.model_call_error is None
    assert backend.calls == []


def test_ac_gen_012_timeout_classified_error_no_internal_retry(repo_root):
    backend = MockBackend([BackendResult(text=None, error_category="timeout", error_message="bounded wait exceeded")])
    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.model_call_error["category"] == "timeout"
    assert len(backend.calls) == 1


def test_ac_gen_013_retry_feedback_is_bare_and_distinct(repo_root):
    backend = MockBackend([BackendResult(text="-----BEGIN FILE: foo.py-----\nx = 1\n-----END FILE-----")])
    result = generate(FakeBundle(), "claude-sonnet-5", ["R-FOO-003"], repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "RETRY_FEEDBACK:" in sent_prompt
    assert json.dumps(["R-FOO-003"]) in sent_prompt
    assert "Gherkin" not in sent_prompt
    assert "rationale" not in sent_prompt.lower()
    assert result.retry_feedback == ["R-FOO-003"]
