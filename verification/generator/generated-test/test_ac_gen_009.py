# hotdocs-criterion: sha256:55511b30f4c7b1a4496f96f92a02acf49d8f74f4dbc00bcf9ab664986b911cfa
import json
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(comp_id, title, sealed, source_path):
    text = (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: " + ("true" if sealed else "false") + "\n"
    )
    if source_path is not None:
        text += "source_path: " + source_path + "\n"
    text += (
        "depends_on: []\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + title + " doubles a number.\n"
    )
    return text


def build_component(repo_root, slug, comp_id, title, prefix, sealed, source_path):
    base = repo_root / "specs" / "components" / slug
    write(base / "component.md", component_md(comp_id, title, sealed, source_path))
    rid = "R-" + prefix + "-001"
    acid = "AC-" + prefix + "-001"
    write(
        base / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        base / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(base / "constraints.md", "# Constraints\n\nNone.\n")


def build_repo(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    # Sealed component with a source_path.
    build_component(repo_root, "foo", "comp-foo", "Foo", "FOO", True, "legacy/foo/")
    write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")
    # Unsealed component with a pinned override file.
    build_component(repo_root, "bar", "comp-bar", "Bar", "BAR", False, None)
    write(repo_root / "gen" / "bar" / "bar.py", "def foo(x):\n    return 2 * x\n")
    write(
        repo_root / "gen" / "bar" / ".overrides.json",
        json.dumps(["bar.py"]) + "\n",
    )


def make_bundle(comp_id):
    return {
        "component_id": comp_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "spec": "Foo doubles a number.\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** \u2014 a test term.",
        "hint_code": None,
    }


@pytest.mark.parametrize(
    "comp_id, slug, expected_words",
    [
        ("comp-foo", "foo", ("sealed",)),
        ("comp-bar", "bar", ("pinned", "override")),
    ],
)
def test_ac_gen_009_refused_before_any_model_call(
    tmp_path, monkeypatch, comp_id, slug, expected_words
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    call_log = tmp_path / "model_calls.log"
    calls = []

    def mock_backend(prompt, model, **params):
        calls.append(prompt)
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "text": "",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    pinned_before = (repo_root / "gen" / "bar" / "bar.py").read_text(encoding="utf-8")
    sealed_before = (repo_root / "legacy" / "foo" / "foo.py").read_text(encoding="utf-8")

    result = generator.generate(
        make_bundle(comp_id),
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The mock model is never called.
    assert calls == []
    assert not call_log.exists() or call_log.read_text(encoding="utf-8") == ""

    # files empty, model_call_error null, refused a reason string naming the exemption.
    files = field(result, "files")
    assert not files
    assert field(result, "model_call_error") is None
    refused = field(result, "refused")
    assert isinstance(refused, str) and refused.strip()
    assert any(word in refused.lower() for word in expected_words), refused

    # Hands-off paths were not clobbered.
    assert (repo_root / "gen" / "bar" / "bar.py").read_text(encoding="utf-8") == pinned_before
    assert (repo_root / "legacy" / "foo" / "foo.py").read_text(encoding="utf-8") == sealed_before