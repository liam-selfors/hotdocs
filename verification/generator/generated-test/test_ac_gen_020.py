# hotdocs-criterion: sha256:2f0bbc4ea468170252d2f5646d87543dbc134ea76e657c330fc24b410fadcbee
import json
import re

import generator


class _Bundle:
    """A SpecBundle-shaped object readable both by attribute and as a mapping."""

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
            setattr(self, name, kwargs[name])

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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_bundle():
    # Deliberately bland content: no dependencies at all (the instruction
    # must be present regardless of depends_on), and no words the
    # assertions look for, so any match comes from generate's own prompt.
    return _Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a1" * 32,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n**R-FOO-001** — foo(x) MUST yield 2 * x.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


TOP_LEVEL_PHRASES = (
    "top-level",
    "top level",
    "toplevel",
    "own return value",
    "return value itself",
    "own top",
)


def test_prompt_instructs_dual_access_for_dependency_top_level_return(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "mock_calls.log"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(prompt) + "\n")
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

    bundle = _make_bundle()
    assert bundle.hint_code is None  # cold mode

    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False

    assert log_path.is_file(), "mock model was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, "expected exactly one model call, got %d" % len(lines)
    prompt = json.loads(lines[0])
    assert isinstance(prompt, str) and prompt

    low = prompt.lower()

    # The prompt as a whole must talk about dual dict-or-attribute access.
    assert "dict" in low, "prompt never mentions dict access"
    assert ("attribute" in low) or ("getattr" in low), "prompt never mentions attribute access"

    # It must forbid a bare attribute access on its own.
    assert ("bare" in low) or (" alone" in low) or ("never" in low), (
        "prompt never forbids a bare attribute access alone"
    )

    # And it must extend that rule explicitly to a dependency's own
    # top-level return value, not only nested values: some mention of the
    # top-level return value must sit near the dict/attribute instruction.
    found = False
    for phrase in TOP_LEVEL_PHRASES:
        start = 0
        while True:
            idx = low.find(phrase, start)
            if idx < 0:
                break
            window = low[max(0, idx - 800): idx + 800]
            if "dict" in window and ("attribute" in window or "getattr" in window):
                found = True
                break
            start = idx + 1
        if found:
            break
    assert found, (
        "prompt does not instruct that a dependency's own top-level return "
        "value must use dual dict-or-attribute access"
    )

    # The instruction concerns values read from dependency calls.
    assert "depend" in low