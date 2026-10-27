"""One test per AC-GEN-* criterion in
specs/components/generator/acceptance/.

Rewritten for D58 against the self-hosted gen/generator/ swap-in itself
-- the nonce lives directly in the prompt (not a separate system_prompt
parameter), dependencies are loaded dynamically from repo_root per call
(R-GEN-014), and the cache payload's exact keys are
component_id/model/prompt_version/files (see conftest.py's docstring).
"""

import json
import shutil

from conftest import FakeBundle, MockBackend, file_block
import generator
from generator import GATE_VERSION, PROMPT_VERSION, generate
import cache_manager


def test_ac_gen_001_cold_prompt_contains_exactly_cold_fields(repo_root):
    backend = MockBackend([file_block("foo.py", "x = 1")])
    bundle = FakeBundle()
    generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "FAKE SPEC TEXT" in sent_prompt
    assert "FAKE INTERFACE TEXT" in sent_prompt
    assert "FAKE CONSTRAINTS TEXT" in sent_prompt
    assert "FAKE GLOSSARY TEXT" in sent_prompt
    assert "## HINT_CODE" not in sent_prompt
    assert "## RETRY_FEEDBACK" not in sent_prompt


def test_ac_gen_002_hint_code_is_a_distinct_section(repo_root):
    backend = MockBackend([file_block("foo.py", "x = 1")])
    bundle = FakeBundle(hint_code={"foo.py": "x = 0"})
    generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "## HINT_CODE" in sent_prompt
    assert '"foo.py"' in sent_prompt and '"x = 0"' in sent_prompt


def test_ac_gen_003_prompt_version_matches_frozen_template(repo_root):
    backend = MockBackend([{"text": "", "model_call_error": None}])
    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.prompt_version == PROMPT_VERSION  # frozen, whatever it currently is (D57: "v4")


def test_ac_gen_004_model_identifier_passed_through_unchanged(repo_root):
    backend_a = MockBackend([{"text": "", "model_call_error": None}])
    backend_b = MockBackend([{"text": "", "model_call_error": None}])
    generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend_a)
    generate(FakeBundle(spec_bundle_hash="sha256:other"), "claude-opus-5", repo_root=repo_root, llm_backend=backend_b)
    assert backend_a.calls[0][1] == "claude-sonnet-5"
    assert backend_b.calls[0][1] == "claude-opus-5"


def test_ac_gen_005_cache_hit_skips_the_model(repo_root):
    bundle = FakeBundle()
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=generator._compute_gate_inputs_hash(None),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    cached_payload = {
        "component_id": "comp-foo", "model": "claude-sonnet-5", "prompt_version": "v1",
        "files": {"foo.py": "x = 1"},
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
    backend = MockBackend([file_block("foo.py", "x = 1")])
    bundle = FakeBundle()
    generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=generator._compute_gate_inputs_hash(None),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    stored = cache_manager.get(cache_key, repo_root=repo_root)
    assert isinstance(stored, cache_manager.CachedResult)
    assert stored.payload["files"] == {"foo.py": "x = 1"}
    # D56 regression: the payload carries every key cache-manager's own
    # schema requires for this gate type (interface/data/CachedResult.md).
    assert set(stored.payload) >= {"component_id", "model", "prompt_version", "files"}


def test_ac_gen_008_model_call_error_surfaces_cleanly(repo_root):
    backend = MockBackend([{"text": None, "model_call_error": {"category": "network", "message": "connection reset"}}])
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
    backend = MockBackend([{"text": None, "model_call_error": {"category": "timeout", "message": "bounded wait exceeded"}}])
    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.model_call_error["category"] == "timeout"
    assert len(backend.calls) == 1


def test_ac_gen_013_retry_feedback_is_bare_and_distinct(repo_root):
    backend = MockBackend([file_block("foo.py", "x = 1")])
    result = generate(FakeBundle(), "claude-sonnet-5", ["R-FOO-003"], repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "## RETRY_FEEDBACK" in sent_prompt
    assert "R-FOO-003" in sent_prompt
    retry_section = sent_prompt[sent_prompt.index("## RETRY_FEEDBACK"):]
    assert "Gherkin" not in retry_section
    assert "rationale" not in retry_section.lower()
    assert result.retry_feedback == ["R-FOO-003"]


def test_ac_gen_014_dependency_usage_is_a_distinct_section(repo_root):
    backend = MockBackend([file_block("foo.py", "x = 1")])
    bundle = FakeBundle(dependency_usage={"comp-bar": "Importable as: `bar`.\n- `bar_get(key: str) -> str`"})
    generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "## DEPENDENCY USAGE" in sent_prompt
    assert "bar_get(key: str) -> str" in sent_prompt
    # Still clearly separate from dependency_interfaces' own section.
    dep_iface_idx = sent_prompt.index("DEPENDENCY INTERFACES")
    dep_usage_idx = sent_prompt.index("DEPENDENCY USAGE")
    assert dep_iface_idx != dep_usage_idx


def test_ac_gen_015_two_repo_roots_in_one_process_do_not_collide(repo_root, tmp_path_factory):
    """R-GEN-014/D57 -- a per-call dynamic dependency load from repo_root
    must not crash on a dataclass-defining dependency (the real bug a
    prior self-regeneration candidate hit), and must not let the second
    repo_root's call see the first one's cached module."""
    other_root = tmp_path_factory.mktemp("other-repo")
    shutil.copytree(repo_root / "gen" / "cache-manager", other_root / "gen" / "cache-manager")
    shutil.copytree(repo_root / "gen" / "llm-endpoint", other_root / "gen" / "llm-endpoint")
    marker_file = other_root / "gen" / "cache-manager" / "cache_manager.py"
    marker_file.write_text(marker_file.read_text(encoding="utf-8") + "\nSANDBOX_MARKER = 'other_root'\n", encoding="utf-8")

    backend_a = MockBackend([file_block("foo.py", "x = 1")])
    backend_b = MockBackend([file_block("foo.py", "x = 2")])
    generate(FakeBundle(component_id="comp-one"), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend_a)
    generate(FakeBundle(component_id="comp-two"), "claude-sonnet-5", repo_root=other_root, llm_backend=backend_b)

    cm_from_repo_root = generator._load_cache_manager(repo_root)
    cm_from_other_root = generator._load_cache_manager(other_root)
    assert not hasattr(cm_from_repo_root, "SANDBOX_MARKER")
    assert getattr(cm_from_other_root, "SANDBOX_MARKER", None) == "other_root"
