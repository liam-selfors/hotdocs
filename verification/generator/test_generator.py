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
import hashlib


def _gate_inputs_hash(retry_feedback):
    """The formula interface/library.md states (R-GEN-005, D209)."""
    material = json.dumps(sorted(retry_feedback or []), sort_keys=True)
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


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
    assert "foo.py" in sent_prompt and "x = 0" in sent_prompt


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
        gate_inputs_hash=_gate_inputs_hash(None),
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
    assert {k: v.rstrip("\n") for k, v in result.files.items()} == {"foo.py": "x = 1"}
    assert backend.calls == []


def test_ac_gen_006_only_commit_cache_writes_the_cache(repo_root):
    """D305 -- generate() never caches; commit_cache does, after a pass."""
    backend = MockBackend([file_block("foo.py", "x = 1")])
    bundle = FakeBundle()
    result = generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=_gate_inputs_hash(None),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    assert isinstance(cache_manager.get(cache_key, repo_root=repo_root), cache_manager.Miss)
    generator.commit_cache(result, repo_root=repo_root)
    stored = cache_manager.get(cache_key, repo_root=repo_root)
    assert isinstance(stored, cache_manager.CachedResult)
    assert {k: v.rstrip("\n") for k, v in stored.payload["files"].items()} == {"foo.py": "x = 1"}
    # D56 regression: the payload carries every key cache-manager's own
    # schema requires for this gate type (interface/data/CachedResult.md).
    assert set(stored.payload) >= {"component_id", "model", "prompt_version", "files"}


def test_ac_gen_008_model_call_error_surfaces_cleanly(repo_root):
    backend = MockBackend([{"text": None, "model_call_error": {"category": "network", "message": "connection reset"}}])
    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.model_call_error == {"category": "network", "message": "connection reset"}
    assert result.files == {}
    assert result.cache_hit is False


def test_ac_gen_008_empty_response_is_a_model_call_error(repo_root):
    backend = MockBackend([{"text": "I cannot help with that.", "model_call_error": None}])
    bundle = FakeBundle()
    result = generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.model_call_error["category"] == "empty_response"
    assert result.files == {}
    assert not (repo_root / "gen" / "foo").exists()
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=_gate_inputs_hash(None),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    assert not isinstance(cache_manager.get(cache_key, repo_root=repo_root), cache_manager.CachedResult)


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


def test_ac_gen_016_output_layout_instruction_is_present(repo_root):
    backend = MockBackend([file_block("foo.py", "x = 1")])
    generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "src/" in sent_prompt and "package" in sent_prompt
    assert "foo.py" in sent_prompt  # the real module name (D268)


def test_ac_gen_019_repo_root_relative_dependency_load_instruction_is_present(repo_root):
    """R-GEN-018/D138 -- every candidate must be told, unconditionally,
    that a dynamic dependency load (bare import, bare-named sys.modules
    lookup, or __file__-relative path) must resolve from repo_root
    instead -- found only after the identical bug recurred independently
    in four separate components' own candidates."""
    backend = MockBackend([file_block("foo.py", "x = 1")])
    generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "repo_root" in sent_prompt
    assert "import <module_name>" in sent_prompt
    assert "sys.modules" in sent_prompt
    assert "__file__" in sent_prompt
    # D159: a sealed dependency lives at its own source_path, not gen/.
    assert "source_path" in sent_prompt


def test_ac_gen_020_dual_access_on_dependency_return_value_instruction_is_present(repo_root):
    """R-GEN-019/D139 -- every candidate must be told that dual
    dict-or-attribute access applies to a dependency's own top-level
    return value too, not only to values nested within it -- found
    after a candidate applied the pattern correctly to nested entries
    but not to the outer return value itself."""
    backend = MockBackend([file_block("foo.py", "x = 1")])
    generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    sent_prompt = backend.calls[0][0]
    assert "dual dict-or-attribute access" in sent_prompt
    assert "top-level return value" in sent_prompt


def test_ac_gen_015_two_repo_roots_in_one_process_do_not_collide(repo_root, tmp_path_factory):
    """R-GEN-014/D57 -- a per-call dynamic dependency load from repo_root
    must not crash on a dataclass-defining dependency (the real bug a
    prior self-regeneration candidate hit), and must not let the second
    repo_root's call see the first one's cached module."""
    other_root = tmp_path_factory.mktemp("other-repo")
    shutil.copytree(repo_root / "gen" / "cache-manager", other_root / "gen" / "cache-manager")
    shutil.copytree(repo_root / "gen" / "llm-endpoint", other_root / "gen" / "llm-endpoint")
    # other_root's cache-manager records each put() to a file, so the test
    # observes which root's copy each call loaded without a private loader.
    marker = other_root / "puts.log"
    cm_dir = other_root / "gen" / "cache-manager"
    cm_file = cm_dir / "cache_manager.py"
    if not cm_file.is_file():  # a package-shaped cache-manager
        cm_file = cm_dir / "cache_manager" / "__init__.py"
    cm_file.write_text(cm_file.read_text(encoding="utf-8") + f"""

_real_put = put
def put(cache_key, result, *, repo_root=None):
    with open({str(marker)!r}, "a", encoding="utf-8") as fh:
        fh.write(str(result.payload.get("component_id")) + "\\n")
    return _real_put(cache_key, result, repo_root=repo_root)
""", encoding="utf-8")

    def run(component_id, module, root, value):
        result = generate(FakeBundle(component_id=component_id, spec_bundle_hash="sha256:" + module),
                          "claude-sonnet-5", repo_root=root,
                          llm_backend=MockBackend([file_block(f"{module}.py", f"x = {value}")]))
        assert result.model_call_error is None, result.model_call_error
        generator.commit_cache(result, repo_root=root)

    run("comp-one", "one", repo_root, 1)
    assert not marker.exists()  # repo_root's own cache-manager, not other_root's
    run("comp-two", "two", other_root, 2)
    assert marker.read_text(encoding="utf-8").split() == ["comp-two"]
    run("comp-three", "three", repo_root, 3)
    assert marker.read_text(encoding="utf-8").split() == ["comp-two"]  # no cached-module leak back


def test_ac_gen_017_hint_mode_never_writes_gen_or_cache(repo_root):
    """R-GEN-016/D81 -- a hint-mode call must not write gen/<component>/
    or the cache, even on a fresh (non-cache-hit) call."""
    backend = MockBackend([file_block("foo.py", "x = 1")])
    bundle = FakeBundle(hint_code={"foo.py": "x = 0"})
    result = generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)

    assert {k: v.rstrip("\n") for k, v in result.files.items()} == {"foo.py": "x = 1"}  # still returned to the caller
    assert not (repo_root / "gen" / "foo").exists()  # never written to disk

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=_gate_inputs_hash(None),
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )
    assert isinstance(cache_manager.get(cache_key, repo_root=repo_root), cache_manager.Miss)
    generator.commit_cache(result, repo_root=repo_root)  # a hint-mode result is never committed
    assert isinstance(cache_manager.get(cache_key, repo_root=repo_root), cache_manager.Miss)


def test_ac_gen_017_hint_mode_still_reads_an_existing_cache_hit(repo_root):
    """A cache hit from an earlier cold-mode call for this exact spec
    state must still be returned in hint mode, with no model call and
    gen/<component>/ left untouched."""
    bundle = FakeBundle(hint_code={"foo.py": "x = 1"})
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=_gate_inputs_hash(None),
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
    assert {k: v.rstrip("\n") for k, v in result.files.items()} == {"foo.py": "x = 1"}
    assert not (repo_root / "gen" / "foo").exists()


def test_ac_gen_018_result_echoes_the_bundles_spec_bundle_hash(repo_root):
    """R-GEN-017/D83 -- provenance-writer has no other way to learn the
    spec_bundle_hash of what was generated."""
    backend = MockBackend([file_block("foo.py", "x = 1")])
    bundle = FakeBundle(spec_bundle_hash="sha256:distinctivevalue")
    result = generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.spec_bundle_hash == "sha256:distinctivevalue"


def test_ac_gen_021_redundant_component_prefix_is_stripped(repo_root):
    """R-GEN-015/D165 -- a candidate restated its own directory
    (`license-scanner/license_scanner.py`), landing the module one level
    too deep where nothing could import it."""
    from conftest import _NONCE_RE

    def _three_files(prompt, model, **params):
        nonce = _NONCE_RE.search(prompt).group("nonce")
        blocks = [
            ("foo-bar/foo_bar.py", "x = 1"),
            ("gen/foo-bar/helpers/__init__.py", "y = 2"),
            ("foo_bar_extra.py", "z = 3"),
        ]
        text = "\n".join(
            f"-----BEGIN FILE {nonce}: {path}-----\n{body}\n-----END FILE {nonce}-----"
            for path, body in blocks
        ) + f"\n-----END REPLY {nonce}-----"
        return {"text": text, "model_call_error": None}

    bundle = FakeBundle(component_id="comp-foo-bar")
    result = generate(bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=MockBackend([_three_files]))

    gen_dir = repo_root / "gen" / "foo-bar"
    assert (gen_dir / "foo_bar.py").read_text().rstrip("\n") == "x = 1"
    assert (gen_dir / "helpers" / "__init__.py").read_text().rstrip("\n") == "y = 2"
    assert (gen_dir / "foo_bar_extra.py").read_text().rstrip("\n") == "z = 3"
    assert not (gen_dir / "foo-bar").exists()
    assert not (gen_dir / "gen").exists()
    assert set(result.files) == {"foo_bar.py", "helpers/__init__.py", "foo_bar_extra.py"}


def test_ac_gen_019_dependencies_fall_back_to_the_tool_root(tmp_path, monkeypatch):
    """D199 -- a project holds only its own components; with no gen/ under
    repo_root, cache-manager and llm-endpoint come from the tool's own gen/."""
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    backend = MockBackend([file_block("foo.py", "x = 1")])
    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=tmp_path, llm_backend=backend)
    assert result.model_call_error is None
    assert (tmp_path / "gen" / "foo" / "foo.py").read_text().strip() == "x = 1"
    assert "tool root" in backend.calls[0][0]


def test_ac_gen_022_truncated_reply_writes_and_caches_nothing(repo_root):
    """D304 -- a reply cut off before its end marker used to drop the
    unclosed file silently and write the rest."""
    from conftest import _NONCE_RE

    def _cut_off(prompt, model, **params):
        nonce = _NONCE_RE.search(prompt).group("nonce")
        return {"text": (f"-----BEGIN FILE {nonce}: foo.py-----\nx = 1\n-----END FILE {nonce}-----\n"
                         f"-----BEGIN FILE {nonce}: helpers.py-----\ny = "), "model_call_error": None}

    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=MockBackend([_cut_off]))
    assert result.model_call_error["category"] == "truncated_response"
    assert "helpers.py" in result.model_call_error["message"]
    assert result.files == {}
    assert not (repo_root / "gen" / "foo").exists()


def test_ac_gen_022_reply_without_the_module_is_missing_module(repo_root):
    backend = MockBackend([file_block("notes.py", "x = 1")])
    result = generate(FakeBundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend)
    assert result.model_call_error["category"] == "missing_module"
    assert not (repo_root / "gen" / "foo").exists()
