# hotdocs-criterion: sha256:dfbd1b65b9136c8a9366c1fa27f9e35f07a71e4f4acd055c4979684d227b2478
import re

import pytest

import test_author


PROBE_SOURCE = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 1\n"
    "        self.tests_reached = 1\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': True, 'findings': [], 'tests_run': 1, 'tests_reached': 1}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
    "    return _Report()\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _plant_probe(repo_root):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(PROBE_SOURCE, encoding="utf-8")


def _bundle(component_id, criterion_id, covers):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "Given a thing\nWhen it runs\nThen it works",
        "requirement_text": "The thing MUST work.",
        "interface": "do_thing() -> str",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _run_and_capture_prompts(tmp_path, monkeypatch, name, bundle):
    repo_root = tmp_path / name
    repo_root.mkdir()
    _plant_probe(repo_root)
    monkeypatch.chdir(repo_root)

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_placeholder():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "model_call_error") is None
    assert prompts, "author_test never called the model backend"
    return prompts


def test_prompt_names_hyphenated_slug_as_underscored_import(tmp_path, monkeypatch):
    bundle = _bundle("comp-foo-bar", "AC-FOO-BAR-001", "R-FOO-BAR-001")
    prompts = _run_and_capture_prompts(tmp_path, monkeypatch, "scenario1", bundle)

    for prompt in prompts:
        assert re.search(r"import foo_bar\b", prompt), (
            "prompt does not state 'import foo_bar'"
        )
        assert "import comp_foo_bar" not in prompt
        assert "import comp-foo-bar" not in prompt


def test_prompt_names_simple_slug_import(tmp_path, monkeypatch):
    bundle = _bundle("comp-semver", "AC-SEMVER-001", "R-SEMVER-001")
    prompts = _run_and_capture_prompts(tmp_path, monkeypatch, "scenario2", bundle)

    for prompt in prompts:
        assert re.search(r"import semver\b", prompt), (
            "prompt does not state 'import semver'"
        )
        assert "import comp_semver" not in prompt