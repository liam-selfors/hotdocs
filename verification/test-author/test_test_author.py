import pytest
"""One test per AC-AUTHOR-* criterion in
specs/components/test-author/acceptance/."""

import dataclasses
import json
import types

from conftest import REPO_ROOT, MockBackend, fake_bundle, fake_bundle_dict, file_block
import spec_bundle_assembler
from test_author import author_test


def _file_field(file_info, key):
    """_rf(result, "file")'s own shape (dict vs. an object with .path/.content)
    has legitimately varied across real regeneration rounds; the real
    consumer (verifier_orchestrator._extract_test_authoring) already
    tolerates both, so this test suite does too rather than coupling to
    one shape."""
    return file_info[key] if isinstance(file_info, dict) else getattr(file_info, key)


def _rf(result, key):
    """author_test's own return value (TestAuthoringResult) may itself
    be a dict or a dataclass instance across real regeneration rounds
    -- same duck-typing convention (D94) as everything else in this
    corpus. Never assume attribute access alone."""
    return result[key] if isinstance(result, dict) else getattr(result, key)


def _body(content):
    """R-AUTHOR-028 (D320): the file is a header line, then the test."""
    first, _, rest = content.partition("\n")
    assert first.startswith("# hotdocs-criterion: sha256:"), content
    return rest


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
        "dependency_interfaces": bundle.dependency_interfaces,
    }
    # The real implementation's own distinguishing internals must not
    # appear anywhere in the bundle fields a model prompt would be built
    # from.
    assert "_REQUIRED_PAYLOAD_KEYS" not in json.dumps(bundle_dict)
    assert set(bundle_dict.keys()) == {
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary", "dependency_interfaces",
    }


def test_ac_author_003_canonical_model_used_regardless_of_generator_model(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    # generator used "claude-opus-5" for this component's current code;
    # author_test is still called with (and must use) the canonical model.
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert backend.calls[0][1] == "claude-sonnet-5"


def test_ac_author_004_cache_hit_skips_the_model(repo_root):
    # Deriving the real CacheKey by hand would couple this test to
    # internal hashing/versioning helpers whose names and signatures
    # have legitimately varied across real regeneration rounds. Instead,
    # populate the cache the same way a real call would -- via author_test
    # itself -- then call again with a backend that must never be used.
    bundle = fake_bundle()
    seeding_backend = MockBackend([file_block("def test_x(): pass")])
    first = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=seeding_backend)
    assert _rf(first, "cache_hit") is False

    backend = MockBackend([])  # must never be called
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert _rf(result, "cache_hit") is True
    assert backend.calls == []
    assert _file_field(_rf(result, "file"), "content") == _file_field(_rf(first, "file"), "content")


def test_ac_author_005_successful_call_is_cached(repo_root):
    # Same reasoning as test_ac_author_004: prove "cached under the
    # correct key" behaviorally -- a second call with a different
    # backend must return the first call's result, never the second
    # backend's -- rather than reconstructing the real CacheKey by hand.
    first_backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    first = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=first_backend)
    assert _body(_file_field(_rf(first, "file"), "content")) == "def test_x(): pass"

    second_backend = MockBackend([file_block("def test_y(): pass")])  # must never be called
    second = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=second_backend)
    assert _rf(second, "cache_hit") is True
    assert second_backend.calls == []
    assert _body(_file_field(_rf(second, "file"), "content")) == "def test_x(): pass"


def test_ac_author_006_output_path_under_generated_test_dir(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    # verifier_orchestrator itself tolerates either an absolute or a
    # repo_root-relative path (it joins only if not already absolute) --
    # this check matches that same tolerance rather than requiring one
    # exact string form.
    reported_path = _file_field(_rf(result, "file"), "path")
    assert reported_path.replace("\\", "/").endswith(
        "verification/foo/generated-test/test_ac_foo_003.py"
    )
    assert "gen/foo" not in reported_path
    assert "compiled" not in reported_path
    assert (repo_root / reported_path).is_file()


def test_ac_author_007_model_call_error_is_distinct(repo_root):
    backend = MockBackend([{"text": None, "model_call_error": {"category": "network", "message": "boom"}}])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert _rf(result, "model_call_error")["category"] == "network"
    assert _rf(result, "model_call_error")["message"] == "boom"
    assert _rf(result, "file") is None
    assert _rf(result, "cache_hit") is False
    assert not (repo_root / "verification" / "foo" / "generated-test").exists()


def test_ac_author_008_api_key_never_appears_in_output(repo_root, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-super-secret-value")
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    result_dict = result if isinstance(result, dict) else dataclasses.asdict(result)
    serialized = json.dumps(result_dict)
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

    assert _rf(result, "model_call_error") is None
    assert _body(_file_field(_rf(result, "file"), "content")).strip() == "def test_x(): pass"
    assert "```" not in _file_field(_rf(result, "file"), "content")
    assert "Sure, here is the test" not in _file_field(_rf(result, "file"), "content")
    assert "Let me know" not in _file_field(_rf(result, "file"), "content")


def test_ac_author_009_no_marker_pair_is_a_distinct_failure(repo_root):
    bundle = fake_bundle()
    backend = MockBackend([
        {"text": "I could not find the right markers so here is some text instead.", "model_call_error": None}
    ])
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert _rf(result, "file") is None
    assert _rf(result, "model_call_error") is not None
    assert not (repo_root / "verification" / "foo" / "generated-test").exists()

    # "Nothing written to cache" proven behaviorally: a second call with
    # matching inputs still reaches the model rather than returning a
    # (nonexistent) cached result from the failed first call.
    retry_backend = MockBackend([file_block("def test_x(): pass")])
    retry = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=retry_backend)
    assert _rf(retry, "cache_hit") is False
    assert len(retry_backend.calls) == 1


def test_ac_author_010_prompt_states_dependency_resolution_convention(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    # Governs faking a DEPENDENCY -- never a claim about importing the
    # component under test itself (D97). Checked on concepts, not exact
    # prose, since wording has legitimately varied across real rounds.
    assert (
        "statically import" in normalized
        or "statically importable" in normalized
        or "no static import" in normalized.lower()
        or "static `import`" in normalized.lower()
        or "static import statement" in normalized.lower()
    )
    assert "dependency" in normalized.lower()
    assert "repo_root>/gen/" in normalized or "gen/<dependency-slug>" in normalized
    # The component under test itself needs no custom loader at all.
    assert "custom loader" in normalized and "component under test" in normalized
    assert "plain" in normalized and "import" in normalized
    # A fake dependency is always written flat, never as a package --
    # closes the real __init__-as-a-module-name confusion D97 found.
    assert "flat-module" in normalized or "flat module" in normalized
    assert "package" in normalized
    assert ("hyphen" in normalized or "`-`" in normalized) and (
        "underscore" in normalized or "`_`" in normalized
    )
    assert "sys.modules" in sent_prompt
    assert "exec_module" in sent_prompt
    # The worked snippet puts the registration assignment textually
    # before the exec_module call -- the one ordering this requirement
    # exists to enforce.
    assert sent_prompt.index("sys.modules[module_name] = module") < sent_prompt.index("exec_module(module)")


def test_ac_author_011_prompt_includes_dependency_interfaces(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle(
        dependency_interfaces={
            "comp-bar": 'do_the_thing(x: int, y: str) -> SomeResult'
        }
    )
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "comp-bar" in sent_prompt
    assert "do_the_thing(x: int, y: str) -> SomeResult" in sent_prompt
    assert "real" in sent_prompt.lower() and "signature" in sent_prompt.lower()


def test_ac_author_011_prompt_builds_with_no_dependencies(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle(dependency_interfaces={})
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert _rf(result, "model_call_error") is None
    sent_prompt = backend.calls[0][0]
    assert "comp-bar" not in sent_prompt


def test_ac_author_012_prompt_states_required_frontmatter_schema(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    assert "component.md" in normalized
    for field in ("id", "title", "status", "owners"):
        assert field in normalized


def test_ac_author_013_prompt_states_sealed_default(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    # D103: defaults to sealed:true unless realizes/capability-linkage
    # is specifically under test -- sidesteps R-LINT-006 and similar
    # rules rather than enumerating them one at a time.
    assert "sealed: true" in normalized or "sealed:true" in normalized or "sealed` " in normalized
    assert "source_path" in normalized
    assert "realizes" in normalized
    assert "P-" in normalized or "P<" in normalized


def test_ac_author_014_prompt_states_flow_style_lists(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    # D104: block-style YAML lists are not recognized as lists at all
    # by this corpus's frontmatter reader -- confirmed the sole cause
    # of 5 of 7 real spec-bundle-assembler test failures.
    assert "flow style" in normalized or "flow-style" in normalized
    assert "block style" in normalized or "block-style" in normalized
    assert "owners" in normalized and "depends_on" in normalized


def test_ac_author_015_prompt_states_fixture_self_check(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    # D104: a standing structural safeguard -- self-check a constructed
    # fixture against spec-linter's own lint() before testing the real
    # behavior, so an invalid fixture fails immediately and legibly.
    assert "lint()" in normalized or "lint(" in normalized
    assert "spec-linter" in normalized
    assert "hard-fail" in normalized or "hard fail" in normalized


def test_ac_author_016_prompt_states_status_enum_all_doc_types_and_acceptance_coverage(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    # D105: status enum stated explicitly.
    assert "draft" in normalized and "ratified" in normalized and "deprecated" in normalized
    # D105: frontmatter rule applies to every document type, not just
    # component.md.
    assert "VAR-" in normalized or "vars/" in normalized
    assert "decisions/D" in normalized or "D<N>" in normalized
    # D105: every requirements/ file needs a matching acceptance/ file.
    assert "requirements/" in normalized and "acceptance/" in normalized
    assert "Covers:" in sent_prompt


def test_ac_author_017_tolerates_bundle_missing_dependency_interfaces(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle_dict = fake_bundle_dict()
    del bundle_dict["dependency_interfaces"]
    bundle = types.SimpleNamespace(**bundle_dict)
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert _rf(result, "model_call_error") is None
    assert _rf(result, "file") is not None

    backend2 = MockBackend([file_block("def test_x(): pass")])
    result2 = author_test(bundle_dict, "claude-sonnet-5", seed=1, repo_root=repo_root, llm_backend=backend2)
    assert _rf(result2, "model_call_error") is None
    assert _rf(result2, "file") is not None


def test_ac_author_018_prompt_states_ratified_needs_last_ratified_commit(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    assert "ratified" in normalized and "last_ratified_commit" in normalized


def test_ac_author_019_never_forwards_seed_to_the_backend(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", seed=7, repo_root=repo_root, llm_backend=backend)

    assert len(backend.calls) == 1
    _prompt, _model, params = backend.calls[0]
    assert "seed" not in params


def test_ac_author_020_rejects_malformed_code(repo_root):
    backend = MockBackend([file_block("def test_x(: this is not valid python")])
    bundle = fake_bundle()
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert _rf(result, "file") is None
    assert _rf(result, "model_call_error")["category"] == "malformed_code"
    assert not (repo_root / "verification" / "foo" / "generated-test").exists()


def test_ac_author_020_rejects_fake_with_wrong_arity(repo_root):
    bundle = fake_bundle(
        dependency_interfaces={"comp-bar": "do_thing(a: int, b: str, c: dict[str, str]) -> bool"}
    )
    backend = MockBackend([file_block(
        "def _fake_do_thing(a, b): pass\n"
        "do_thing = _fake_do_thing\n"
        "def test_x(): pass"
    )])
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert _rf(result, "file") is None
    assert _rf(result, "model_call_error")["category"] == "fake_signature_mismatch"
    assert "do_thing" in _rf(result, "model_call_error")["message"]


def test_ac_author_020_accepts_fake_with_matching_arity(repo_root):
    bundle = fake_bundle(
        dependency_interfaces={"comp-bar": "do_thing(a: int, b: str, c: dict[str, str]) -> bool"}
    )
    backend = MockBackend([file_block(
        "def _fake_do_thing(a, b, c): pass\n"
        "do_thing = _fake_do_thing\n"
        "def test_x(): pass"
    )])
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert _rf(result, "model_call_error") is None
    assert _rf(result, "file") is not None


def test_ac_author_020_rejects_wrong_arity_fake_written_as_a_string_literal(repo_root):
    # D113: a fake is normally written to a separate module file as
    # source text, not defined live in the test's own module -- the
    # arity check must see inside a string literal too, not only
    # top-level code.
    bundle = fake_bundle(
        dependency_interfaces={"comp-bar": "do_thing(a: int, b: str, c: dict[str, str]) -> bool"}
    )
    fake_source_literal = (
        'FAKE_SOURCE = """\n'
        "def do_thing(a, b):\n"
        "    return True\n"
        '"""\n'
    )
    backend = MockBackend([file_block(fake_source_literal + "\ndef test_x(): pass")])
    result = author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert _rf(result, "file") is None
    assert _rf(result, "model_call_error")["category"] == "fake_signature_mismatch"
    assert "do_thing" in _rf(result, "model_call_error")["message"]


def test_ac_author_021_prompt_states_dual_access_for_targets_own_return_value(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    assert "dual" in normalized.lower()
    assert "target" in normalized.lower()
    assert "dict" in normalized and "attribute" in normalized


def test_ac_author_022_prompt_forbids_guessed_sys_modules_assertions(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    assert "sys.modules" in sent_prompt
    assert "record" in normalized.lower()
    assert "guess" in normalized.lower()


def test_ac_author_023_prompt_states_write_time_window_truncation(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    assert "truncat" in normalized.lower()
    assert "precision" in normalized.lower()
    assert "before" in normalized.lower() and "after" in normalized.lower()


def test_ac_author_024_prompt_states_file_based_invocation_log(repo_root):
    """R-AUTHOR-024/D144 -- a first fix (D143) told tests to read a
    fake's invocation back via sys.modules[module_name] under the
    bare dependency name, which is itself the exact guessed-key
    failure R-AUTHOR-022 already forbids (a correct candidate may key
    sys.modules dynamically, per R-GEN-018). Confirming invocation
    must instead use a file the test controls, never any in-process
    sys.modules lookup."""
    backend = MockBackend([file_block("def test_x(): pass")])
    bundle = fake_bundle()
    author_test(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    normalized = " ".join(sent_prompt.split())
    assert "file" in normalized.lower() and "invocation" in normalized.lower()
    assert "sys.modules" in sent_prompt
    assert "in-process" in normalized.lower() or "in process" in normalized.lower()


@pytest.mark.parametrize("fake, ok", [
    ("def scan(component_id, repo_root): pass", True),
    ("def scan(repo_root): pass", True),
    ("def scan(a, b, c): pass", False),
])
def test_ac_author_020_name_shared_by_two_dependencies_accepts_either_arity(repo_root, fake, ok):
    """D166 -- license-scanner's scan(component_id, repo_root) and
    secret-scanner's scan(repo_root) share a name; a fake of either
    must be accepted, and a fake fitting neither still rejected."""
    interfaces = {
        "comp-license-scanner": "scan(component_id: str, repo_root: Path) -> LicenseScanResult",
        "comp-secret-scanner": "scan(repo_root: Path) -> SecretScanResult",
    }
    # One fresh repo_root per case: a shared one would serve later cases
    # from test-author's own cache without re-validating them.
    backend = MockBackend([file_block(fake + "\ndef test_x(): pass")])
    result = author_test(fake_bundle(dependency_interfaces=interfaces), "claude-sonnet-5",
                         repo_root=repo_root, llm_backend=backend)
    if ok:
        assert _rf(result, "model_call_error") is None, fake
    else:
        assert _rf(result, "model_call_error")["category"] == "fake_signature_mismatch"


@pytest.mark.parametrize("component_id, module", [("comp-foo-bar", "foo_bar"), ("comp-semver", "semver")])
def test_ac_author_025_prompt_names_the_component_under_tests_module(repo_root, component_id, module):
    """D189 -- the component under test's module is its slug with hyphens
    replaced by underscores. A real external project's five generated
    tests all did `import comp_semver` because the prompt never said."""
    backend = MockBackend([file_block("def test_x(): pass")])
    author_test(fake_bundle(component_id=component_id), "claude-sonnet-5",
                repo_root=repo_root, llm_backend=backend)
    sent_prompt = backend.calls[0][0]
    assert f"import {module}" in sent_prompt
    # The prompt may warn that the id-derived name is wrong; it must never
    # offer it as the import.
    assert f"import comp_{module}" not in sent_prompt


@pytest.mark.parametrize("as_dict", [False, True])
def test_ac_author_026_explicit_module_names_replace_the_derived_one(repo_root, as_dict):
    """D198 -- a capability scenario's component_id names no module, so
    the caller passes the realizing components' modules."""
    make = fake_bundle_dict if as_dict else fake_bundle
    backend = MockBackend([file_block("def test_x(): pass")])
    author_test(make(component_id="capabilities/P-SLUGS", module_names=["slugify", "url_tools"]),
                "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    sent_prompt = backend.calls[0][0]
    assert "import slugify" in sent_prompt
    assert "import url_tools" in sent_prompt
    assert "import capabilities" not in sent_prompt


def test_ac_author_026_empty_module_names_falls_back_to_the_slug(repo_root):
    backend = MockBackend([file_block("def test_x(): pass")])
    author_test(fake_bundle(component_id="comp-semver", module_names=[]), "claude-sonnet-5",
                repo_root=repo_root, llm_backend=backend)
    assert "import semver" in backend.calls[0][0]


def test_d199_dependencies_fall_back_to_the_tool_root(tmp_path, monkeypatch):
    """D199 -- a project holds only its own components; with no gen/ under
    repo_root, cache-manager and llm-endpoint come from the tool's own gen/."""
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    backend = MockBackend([file_block("def test_x(): pass")])
    result = author_test(fake_bundle(), "claude-sonnet-5", repo_root=tmp_path, llm_backend=backend)
    assert _rf(result, "model_call_error") is None
    assert _rf(result, "file") is not None
