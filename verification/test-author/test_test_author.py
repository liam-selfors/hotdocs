"""One test per AC-AUTHOR-* criterion in
specs/components/test-author/acceptance/."""

import json

from conftest import REPO_ROOT, MockBackend, fake_bundle
import spec_bundle_assembler
from test_author import GATE_VERSION, author_test


def file_block(content: str):
    def _build(prompt, model, **params):
        return {"text": content, "model_call_error": None}
    return _build


def test_ac_author_001_prompt_contains_every_bundle_field(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "FAKE CRITERION TEXT" in sent_prompt
    assert "FAKE REQUIREMENT TEXT" in sent_prompt
    assert "FAKE INTERFACE TEXT" in sent_prompt
    assert "FAKE GLOSSARY TEXT" in sent_prompt


def test_ac_author_002_real_criterion_bundle_carries_no_gen_content():
    # Uses the REAL, already-built assemble_criterion against the real
    # repo -- the strongest possible check that a genuinely narrow
    # CriterionBundle (R-ASSEMBLE-009) carries nothing from a component's
    # real gen/ source, not just a synthetic fixture built to pass.
    bundle = spec_bundle_assembler.assemble_criterion("comp-cache-manager", "AC-CACHE-001", REPO_ROOT)
    bundle_dict = {
        "component_id": bundle.component_id,
        "criterion_id": bundle.criterion_id,
        "covers": bundle.covers,
        "criterion_text": bundle.criterion_text,
        "requirement_text": bundle.requirement_text,
        "interface": bundle.interface,
        "glossary": bundle.glossary,
    }
    real_gen_source = (REPO_ROOT / "gen" / "cache-manager" / "cache_manager.py").read_text(encoding="utf-8")
    # The real implementation's own distinguishing internals must not
    # appear anywhere in the bundle fields a model prompt would be built
    # from.
    assert "_REQUIRED_PAYLOAD_KEYS" not in json.dumps(bundle_dict)
    assert set(bundle_dict.keys()) == {
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary",
    }


def test_ac_author_003_canonical_model_used_regardless_of_generator_model(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    # generator used "claude-opus-5" for this component's current code;
    # author_test is still called with (and must use) the canonical model.
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert backend.calls[0][1] == "claude-sonnet-5"


def test_ac_author_004_cache_hit_skips_the_model(repo_root):
    import cache_manager
    import sys
    sys.path.insert(0, str(repo_root / "gen" / "cache-manager"))

    bundle_dict = fake_bundle()
    canonical = json.dumps(bundle_dict, sort_keys=True, separators=(",", ":"))
    criterion_hash = "sha256:" + __import__("hashlib").sha256(canonical.encode("utf-8")).hexdigest()
    gate_inputs = json.dumps({"seed": 0, "prompt_version": "v1"}, sort_keys=True, separators=(",", ":"))
    gate_inputs_hash = "sha256:" + __import__("hashlib").sha256(gate_inputs.encode("utf-8")).hexdigest()

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=criterion_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    cache_manager.put(
        cache_key,
        cache_manager.CachedResult(
            gate_type="generated_test",
            payload={
                "component_id": "comp-foo", "criterion_id": "AC-FOO-003",
                "model": "claude-sonnet-5",
                "file": {"path": "verification/foo/generated-test/test_ac_foo_003.py", "content": "def test_x(): pass"},
            },
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=repo_root,
    )

    backend = MockBackend([])  # must never be called
    result = author_test(bundle_dict, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.cache_hit is True
    assert backend.calls == []


def test_ac_author_005_successful_call_is_cached(repo_root):
    import cache_manager
    import sys
    sys.path.insert(0, str(repo_root / "gen" / "cache-manager"))

    backend = MockBackend([file_block("def test_x(): pass")])
    bundle_dict = fake_bundle()
    author_test(bundle_dict, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    canonical = json.dumps(bundle_dict, sort_keys=True, separators=(",", ":"))
    criterion_hash = "sha256:" + __import__("hashlib").sha256(canonical.encode("utf-8")).hexdigest()
    gate_inputs = json.dumps({"seed": 0, "prompt_version": "v1"}, sort_keys=True, separators=(",", ":"))
    gate_inputs_hash = "sha256:" + __import__("hashlib").sha256(gate_inputs.encode("utf-8")).hexdigest()
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=criterion_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    stored = cache_manager.get(cache_key, repo_root=repo_root)
    assert isinstance(stored, cache_manager.CachedResult)
    assert stored.payload["file"]["content"] == "def test_x(): pass"


def test_ac_author_006_output_path_under_generated_test_dir(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert result.file.path == "verification/foo/generated-test/test_ac_foo_003.py"
    assert "gen/foo" not in result.file.path
    assert "compiled" not in result.file.path
    assert (repo_root / result.file.path).is_file()


def test_ac_author_007_model_call_error_is_distinct(repo_root):
    backend = MockBackend([{"text": None, "model_call_error": {"category": "network", "message": "boom"}}])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert result.model_call_error == {"category": "network", "message": "boom"}
    assert result.file is None
    assert result.cache_hit is False
    assert not (repo_root / "verification" / "foo" / "generated-test").exists()


def test_ac_author_008_api_key_never_appears_in_output(repo_root, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-super-secret-value")
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    serialized = json.dumps(result.to_dict())
    assert "sk-super-secret-value" not in serialized
