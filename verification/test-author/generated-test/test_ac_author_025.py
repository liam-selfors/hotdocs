# hotdocs-criterion: sha256:90357a633065d916a51634c5421b9f4e06dc2c3dcb8156d1768ef41d4d9f2d1f
import re

import pytest

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

PROBE_SOURCE = (
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
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
    "    return _Report()\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(component_id, slug_upper):
    return {
        "component_id": component_id,
        "criterion_id": "AC-" + slug_upper + "-001",
        "covers": "R-" + slug_upper + "-001",
        "criterion_text": "Given x When y Then z",
        "requirement_text": "R-" + slug_upper + "-001 — The thing MUST work.",
        "interface": "# Library\n\n```\ndo_thing() -> int\n```\n",
        "glossary": "",
        "dependency_interfaces": {},
    }


def run_and_capture_prompts(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(PROBE_SOURCE, encoding="utf-8")
    monkeypatch.chdir(repo_root)

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
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
    assert prompts, "author_test never called the model"
    return prompts


def test_prompt_names_module_with_hyphens_as_underscores(tmp_path, monkeypatch):
    bundle = make_bundle("comp-foo-bar", "FOO-BAR")
    prompts = run_and_capture_prompts(tmp_path, monkeypatch, bundle)
    for prompt in prompts:
        assert "import foo_bar" in prompt
        assert re.search(r"import\s+comp_foo_bar\b", prompt) is None
        assert re.search(r"import\s+comp-foo-bar\b", prompt) is None
        assert re.search(r"import\s+foo-bar\b", prompt) is None


def test_prompt_names_single_word_module(tmp_path, monkeypatch):
    bundle = make_bundle("comp-semver", "SEMVER")
    prompts = run_and_capture_prompts(tmp_path, monkeypatch, bundle)
    for prompt in prompts:
        assert "import semver" in prompt
        assert re.search(r"import\s+comp_semver\b", prompt) is None