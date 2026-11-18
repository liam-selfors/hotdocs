# hotdocs-criterion: sha256:6b331b90b7ec95d4b0f51c7299165b0a9bcfa8e56c04eec8ef9537cf0b76fa97
"""AC-GEN-021 (covers R-GEN-015): generator strips one redundant leading
`gen/<component>/` or `<component>/` prefix from returned file paths before
writing, and rewrites no other path."""

import re
from pathlib import Path

import generator


SLUG = "foo-bar"
COMPONENT_ID = "comp-foo-bar"


class Bundle:
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
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        return getattr(self, key)

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


def make_bundle():
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "ac0021" + "0" * 58,
        spec="# Foo Bar\n\n## Purpose\n\nFoo bar does foo bar things.\n\n"
        "# R-FOO-BAR-001\n\n**R-FOO-BAR-001** — `foo_bar(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo_bar(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


RETURNED_FILES = {
    "foo-bar/foo_bar.py": "def foo_bar(x):\n    return 2 * x\n",
    "gen/foo-bar/helpers/__init__.py": "HELPER = 1\n",
    "foo_bar_extra.py": "EXTRA = 2\n",
}


def make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        parts = []
        for path, content in RETURNED_FILES.items():
            parts.append("-----BEGIN FILE " + nonce + ": " + path + "-----")
            parts.append(content.rstrip("\n"))
            parts.append("-----END FILE " + nonce + "-----")
        parts.append("-----END REPLY " + nonce + "-----")
        text = "\n".join(parts) + "\n"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_redundant_component_prefix_is_stripped_once(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "backend_calls.log"

    result = generator.generate(
        make_bundle(),
        "mock-model",
        None,
        repo_root=repo_root,
        llm_backend=make_backend(log_path),
    )

    # The mock model was actually called (no cache hit, no refusal).
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("called") >= 1
    assert field(result, "refused") is None
    assert field(result, "model_call_error") is None
    assert field(result, "cache_hit") is False

    out_dir = repo_root / "gen" / SLUG
    assert (out_dir / "foo_bar.py").is_file()
    assert (out_dir / "helpers" / "__init__.py").is_file()
    assert (out_dir / "foo_bar_extra.py").is_file()

    assert (out_dir / "foo_bar.py").read_text(encoding="utf-8").strip() == \
        RETURNED_FILES["foo-bar/foo_bar.py"].strip()
    assert (out_dir / "helpers" / "__init__.py").read_text(encoding="utf-8").strip() == \
        RETURNED_FILES["gen/foo-bar/helpers/__init__.py"].strip()
    assert (out_dir / "foo_bar_extra.py").read_text(encoding="utf-8").strip() == \
        RETURNED_FILES["foo_bar_extra.py"].strip()

    nested_component = out_dir / "foo-bar"
    nested_gen = out_dir / "gen"
    if nested_component.exists():
        assert [p for p in nested_component.rglob("*") if p.is_file()] == []
    if nested_gen.exists():
        assert [p for p in nested_gen.rglob("*") if p.is_file()] == []
    assert not nested_component.exists()
    assert not nested_gen.exists()