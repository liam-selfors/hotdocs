# hotdocs-criterion: sha256:296ca67b813232de5b35276ac95c9d7957d6759f83c6ed98eccb12e43b394bf5
import re

import pytest

import generator


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


class FakeBundle:
    """An object with the SpecBundle fields, readable by attribute or by key."""

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

    def __contains__(self, key):
        return key in self._FIELDS

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


def _write_fixture(repo_root):
    (repo_root / "specs" / "components" / "foo").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    (repo_root / "specs" / "components" / "foo" / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: [comp-bar]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
        encoding="utf-8",
    )


def test_ac_gen_001_cold_prompt_built_only_from_bundle_sections(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    bundle = FakeBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a" * 64,
        spec="SPEC-MARK",
        interface="IFACE-MARK",
        constraints="CONS-MARK",
        dependency_interfaces={"comp-bar": "DI-MARK"},
        dependency_context={"comp-bar": "DC-MARK"},
        dependency_usage={"comp-bar": ""},
        vars={"VAR-X": "VAR-MARK"},
        glossary="GLOSS-MARK",
        hint_code=None,
    )

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32})", prompt) or re.search(
            r"\b([0-9a-f]{32})\b", prompt
        )
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert len(recorded) >= 1, "mock model was never called"
    prompt = recorded[0]
    lines = prompt.split("\n")

    assert section(prompt, "## SPEC") == "SPEC-MARK"
    assert section(prompt, "## DEPENDENCY CONTEXT") == "### comp-bar\nDC-MARK"

    assert section(prompt, "## INTERFACE") == "IFACE-MARK"
    assert section(prompt, "## CONSTRAINTS") == "CONS-MARK"
    assert section(prompt, "## DEPENDENCY INTERFACES") == "### comp-bar\nDI-MARK"
    assert section(prompt, "## VARS") == "### VAR-X\nVAR-MARK"
    assert section(prompt, "## GLOSSARY") == "GLOSS-MARK"

    assert "## DEPENDENCY USAGE" not in lines
    assert "## HINT_CODE" not in lines
    assert "## RETRY_FEEDBACK" not in lines