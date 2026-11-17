# hotdocs-criterion: sha256:fd31aa524571c8746ee162f860de81fb55c923838df84727c54fc3733477189e
import re
import uuid
from pathlib import Path

import generator


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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_bundle():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        "spec": "# Foo\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "# Constraints\n\nNone.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** \u2014 a test term.",
        "hint_code": None,
    }


def _write_fixture(repo_root):
    comp_dir = Path(repo_root) / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    glossary = Path(repo_root) / "specs" / "glossary.md"
    glossary.write_text("# Glossary\n\n- **Foo** \u2014 a test term.\n", encoding="utf-8")


def _extract_nonce(prompt):
    m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    m = re.search(r"(?<![0-9a-f])([0-9a-f]{32})(?![0-9a-f])", prompt)
    if m:
        return m.group(1)
    return uuid.uuid4().hex


def test_prompt_contains_nothing_more_and_mutation_testing(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    received = []

    def mock_backend(prompt, model, **params):
        received.append(prompt)
        nonce = _extract_nonce(prompt)
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

    bundle = _make_bundle()
    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert result is not None
    assert len(received) >= 1, "mock model was never called"
    prompt = received[0]
    assert isinstance(prompt, str)
    assert "nothing more" in prompt
    assert "mutation testing" in prompt