# hotdocs-criterion: sha256:2661491a3726dc87d0a772fce8585cbd6cc854422aebc72adb032dd0725d5e52
"""AC-GEN-018 / R-GEN-017: GenerationResult.spec_bundle_hash echoes bundle.spec_bundle_hash."""

import re
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A SpecBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        if m is None:
            m = re.search(r"(?<![0-9a-f])([0-9a-f]{32})(?![0-9a-f])", prompt)
        nonce = m.group(1) if m else "nonce"
        text = (
            "Here is the implementation.\n"
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

    return backend


def make_bundle(spec_bundle_hash):
    return Bundle(
        component_id="comp-foo",
        spec_bundle_hash=spec_bundle_hash,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


@pytest.mark.parametrize(
    "known_hash",
    [
        "sha256:" + "ab" * 32,
        "sha256:" + "0123456789abcdef" * 4,
    ],
)
def test_generation_result_echoes_bundle_spec_bundle_hash(tmp_path, monkeypatch, known_hash):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "backend_calls.log"

    bundle = make_bundle(known_hash)
    result = generator.generate(
        bundle,
        "mock:model",
        repo_root=repo_root,
        llm_backend=make_backend(log_path),
    )

    # The mock model was actually called and produced valid files.
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("call") >= 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    files = field(result, "files")
    assert files

    # The Then clause: exact echo of the bundle's own spec_bundle_hash.
    assert field(result, "spec_bundle_hash") == known_hash
    assert field(result, "spec_bundle_hash") == bundle.spec_bundle_hash