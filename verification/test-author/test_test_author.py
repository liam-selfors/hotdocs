"""One test per AC-AUTHOR-* criterion in
specs/components/test-author/acceptance/."""

import dataclasses
import json

from conftest import REPO_ROOT, MockBackend, fake_bundle, fake_bundle_dict, file_block
import spec_bundle_assembler
from test_author import (
    GATE_VERSION,
    author_test,
    _criterion_content_hash as _criterion_hash,
    _gate_inputs_hash,
)


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
    import sys
    sys.path.insert(0, str(repo_root / "gen" / "cache-manager"))
    import cache_manager

    bundle = fake_bundle()
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=_criterion_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(0),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    cache_manager.put(
        cache_key,
        cache_manager.CachedResult(
            gate_type="generated_test",
            payload={
                "component_id": "comp-foo", "criterion_id": "AC-FOO-003",
                "model": "claude-sonnet-5", "seed": 0, "prompt_version": "v2",
                "file": {"path": "verification/foo/generated-test/test_ac_foo_003.py", "content": "def test_x(): pass"},
            },
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=repo_root,
    )

    backend = MockBackend([])  # must never be called
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.cache_hit is True
    assert backend.calls == []


def test_ac_author_005_successful_call_is_cached(repo_root):
    import sys
    sys.path.insert(0, str(repo_root / "gen" / "cache-manager"))
    import cache_manager

    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=_criterion_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(0),
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

    assert result.file["path"] == "verification/foo/generated-test/test_ac_foo_003.py"
    assert "gen/foo" not in result.file["path"]
    assert "compiled" not in result.file["path"]
    assert (repo_root / result.file["path"]).is_file()


def test_ac_author_007_model_call_error_is_distinct(repo_root):
    backend = MockBackend([{"text": None, "model_call_error": {"category": "network", "message": "boom"}}])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert result.model_call_error["category"] == "network"
    assert result.model_call_error["message"] == "boom"
    assert result.file is None
    assert result.cache_hit is False
    assert not (repo_root / "verification" / "foo" / "generated-test").exists()


def test_ac_author_008_api_key_never_appears_in_output(repo_root, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-super-secret-value")
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    serialized = json.dumps(dataclasses.asdict(result))
    assert "sk-super-secret-value" not in serialized


def test_ac_author_009_strips_fence_and_narration_around_markers(repo_root):
    backend = MockBackend([
        file_block(
            "def test_x(): pass",
            wrapper="Sure, here is the test:\n\n```python\n{marked}\n```\n\nLet me know if you need anything else.",
        )
    ])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert result.model_call_error is None
    assert result.file["content"].strip() == "def test_x(): pass"
    assert "```" not in result.file["content"]
    assert "Sure, here is the test" not in result.file["content"]
    assert "Let me know" not in result.file["content"]


def test_ac_author_009_no_marker_pair_is_a_distinct_failure(repo_root):
    import sys
    sys.path.insert(0, str(repo_root / "gen" / "cache-manager"))
    import cache_manager

    backend = MockBackend([
        {"text": "I could not find the right markers so here is some text instead.", "model_call_error": None}
    ])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert result.file is None
    assert result.model_call_error is not None
    assert not (repo_root / "verification" / "foo" / "generated-test").exists()

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=_criterion_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(0),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    assert isinstance(cache_manager.get(cache_key, repo_root=repo_root), cache_manager.Miss)


def test_ac_author_010_prompt_states_dependency_resolution_convention(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(backend.calls[0][0].split())
    # Governs faking a DEPENDENCY -- never a claim about importing the
    # component under test itself (D97).
    assert "No dependency is statically importable" in normalized
    assert "gen/<dependency-slug>/<module_name>.py" in normalized
    # The component under test itself needs no custom loader at all.
    assert "plain import statement" in normalized
    assert "Never write a custom loader for the component under test itself" in normalized
    # A fake dependency is always written flat, never as a package --
    # closes the real __init__-as-a-module-name confusion D97 found.
    assert "Always write the fake in the flat-module shape, never the package shape" in normalized
    assert 'never a literal "__init__"' in normalized
    assert "sys.modules" in sent_prompt
    assert "exec_module" in sent_prompt
    # The worked snippet puts the registration assignment textually
    # before the exec_module call -- the one ordering this requirement
    # exists to enforce.
    assert sent_prompt.index("sys.modules[module_name] = module") < sent_prompt.index("exec_module(module)")
