# hotdocs-criterion: sha256:dfbd1b65b9136c8a9366c1fa27f9e35f07a71e4f4acd055c4979684d227b2478
import re

import pytest

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PROBE_STAND_IN = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 1\n"
    "        self.tests_reached = 1\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
    "    return _Report()\n"
)


def _plant_probe(repo_root):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(PROBE_STAND_IN, encoding="utf-8")


def _make_backend(prompts):
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

    return backend


def _bundle(component_id, criterion_id, covers):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "Given an input\nWhen the operation runs\nThen it returns a value",
        "requirement_text": "The operation MUST return a value.",
        "interface": "# Library\n\n```\nfrob(x: str) -> str\n```\n",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _prompts_for(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path
    _plant_probe(repo_root)
    monkeypatch.chdir(repo_root)
    prompts = []
    test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=_make_backend(prompts)
    )
    assert prompts, "author_test never called the model"
    return prompts


def test_hyphenated_component_id_imports_underscored_slug(tmp_path, monkeypatch):
    bundle = _bundle("comp-foo-bar", "AC-FOO-BAR-001", "R-FOO-BAR-001")
    prompts = _prompts_for(tmp_path, monkeypatch, bundle)
    for prompt in prompts:
        assert re.search(r"import foo_bar(?![A-Za-z0-9_])", prompt), prompt
        assert "import comp_foo_bar" not in prompt


def test_single_word_component_id_imports_slug(tmp_path, monkeypatch):
    bundle = _bundle("comp-semver", "AC-SEMVER-001", "R-SEMVER-001")
    prompts = _prompts_for(tmp_path, monkeypatch, bundle)
    for prompt in prompts:
        assert re.search(r"import semver(?![A-Za-z0-9_])", prompt), prompt
        assert "import comp_semver" not in prompt