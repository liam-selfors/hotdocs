# hotdocs-criterion: sha256:c7c1cbd1bfafd810e7c71f1bdfa14117b9bd2da1101f75dedb8a2e282861244d
import re
import uuid

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle:
    """An object with the SpecBundle fields that also reads as a mapping."""

    _FIELDS = (
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


def make_cold_bundle():
    return Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )


class RecordingMock:
    def __init__(self):
        self.prompts = []

    def __call__(self, prompt, model, **params):
        self.prompts.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)
    return repo_root


def test_prompt_instructs_dynamic_dependency_loads_resolve_from_repo_root(isolated):
    repo_root = isolated
    bundle = make_cold_bundle()
    mock = RecordingMock()

    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=mock
    )

    assert len(mock.prompts) >= 1, "mock model was never called"
    prompt = mock.prompts[0]
    assert isinstance(prompt, str)

    # The bundle has no dependencies and none of these words, so the
    # instruction must come from the generator's own fixed instructions
    # ("regardless of depends_on").
    for text in (bundle.spec, bundle.interface, bundle.constraints, bundle.glossary):
        assert "repo_root" not in text
        assert "sys.modules" not in text
        assert "__file__" not in text

    assert "repo_root" in prompt
    assert "sys.modules" in prompt
    assert "__file__" in prompt
    assert "import" in prompt
    assert re.search(r"tool", prompt, re.IGNORECASE), "prompt never mentions the tool root fallback"

    # Instruction lives in the fixed part, before the bundle-derived sections.
    lines = prompt.split("\n")
    assert "## SPEC" in lines
    spec_index = prompt.index("\n## SPEC\n") if "\n## SPEC\n" in prompt else prompt.index("## SPEC")
    fixed = prompt[:spec_index]
    assert "repo_root" in fixed
    assert "sys.modules" in fixed
    assert "__file__" in fixed

    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None


def test_generate_completes_without_gen_dir_in_repo_root(isolated):
    repo_root = isolated
    assert not (repo_root / "gen").exists()
    bundle = make_cold_bundle()
    mock = RecordingMock()

    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=mock
    )

    assert len(mock.prompts) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    files = field(result, "files")
    assert files
    assert "foo.py" in files
    assert "return 2 * x" in files["foo.py"]
    assert field(result, "component_id") == "comp-foo"
    assert field(result, "spec_bundle_hash") == bundle.spec_bundle_hash