# hotdocs-criterion: sha256:da2a43e0d7b465d3e5593949526e6b3a1a5a46fd753028a7f736a9796ee28a38
import re
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
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
    "Foo doubles a number.\n"
)

GLOSSARY_MD = "# Glossary\n\n- **Foo** — a test term.\n"


def write_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
        encoding="utf-8",
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD, encoding="utf-8")


def make_success_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})", prompt)
        if m is None:
            m = re.search(r"(?<![0-9a-f])([0-9a-f]{32})(?![0-9a-f])", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "Here is the code.\n"
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


def make_error_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "mock failure"},
        }

    return backend


BUNDLES = [
    {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "# Constraints\n\nNone.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "hint_code": None,
    },
    {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "b" * 64,
        "spec": "# Foo\n\nSomething else entirely.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "# Constraints\n\nMust be fast.",
        "dependency_interfaces": {"comp-bar": "# Library\n\nbar() -> None"},
        "dependency_context": {"comp-bar": "Bar does bar things."},
        "dependency_usage": {"comp-bar": ""},
        "vars": {"VAR-FOO-URL": "The foo URL."},
        "glossary": "",
        "hint_code": None,
    },
]


def test_prompt_version_constant_is_declared():
    assert isinstance(generator.PROMPT_VERSION, str)
    assert generator.PROMPT_VERSION != ""


@pytest.mark.parametrize("bundle", BUNDLES)
@pytest.mark.parametrize("retry_feedback", [None, ["R-FOO-001"]])
def test_prompt_version_matches_frozen_template_on_success(
    tmp_path, monkeypatch, bundle, retry_feedback
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    write_fixture(tmp_path)
    calls = []
    result = generator.generate(
        dict(bundle),
        "claude-sonnet-5",
        retry_feedback,
        repo_root=tmp_path,
        llm_backend=make_success_backend(calls),
    )
    assert field(result, "prompt_version") == generator.PROMPT_VERSION
    # The frozen template sent to the model declares this same version.
    assert len(calls) == 1
    assert ("PROMPT_VERSION: " + generator.PROMPT_VERSION) in calls[0].split("\n")


def test_prompt_version_matches_on_model_call_error(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    write_fixture(tmp_path)
    calls = []
    bundle = dict(BUNDLES[0])
    bundle["spec_bundle_hash"] = "sha256:" + "c" * 64
    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=tmp_path,
        llm_backend=make_error_backend(calls),
    )
    assert field(result, "model_call_error") is not None
    assert field(result, "prompt_version") == generator.PROMPT_VERSION