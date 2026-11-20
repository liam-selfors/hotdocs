# hotdocs-criterion: sha256:e3e24324b477363a859498c64a754d19de3181b99de4bf38d2da344f24421ee8
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
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return _Report()\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _bundle(component_id, slug_upper):
    return {
        "component_id": component_id,
        "criterion_id": "AC-" + slug_upper + "-001",
        "covers": "R-" + slug_upper + "-001",
        "criterion_text": "Given something\nWhen it runs\nThen it works",
        "requirement_text": "The component MUST work.",
        "interface": "do_thing(x: int) -> int",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _capture_prompts(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(PROBE_SOURCE, encoding="utf-8")

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        n = nonces[-1] if nonces else "0" * 32
        text = (
            "-----BEGIN FILE " + n + "-----\n"
            "def test_placeholder():\n    assert True\n"
            "\n-----END FILE " + n + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=backend
    )
    assert prompts, "author_test never called the model backend"
    return prompts


def test_prompt_names_foo_bar_module_concretely(tmp_path, monkeypatch):
    bundle = _bundle("comp-foo-bar", "FOO-BAR")
    prompts = _capture_prompts(tmp_path, monkeypatch, bundle)
    prompt = prompts[0]

    assert re.search(r"import foo_bar\b", prompt), (
        "prompt does not state 'import foo_bar'"
    )
    for p in prompts:
        assert "import comp_foo_bar" not in p
        assert "import comp-foo-bar" not in p


def test_prompt_names_semver_module_concretely(tmp_path, monkeypatch):
    bundle = _bundle("comp-semver", "SEMVER")
    prompts = _capture_prompts(tmp_path, monkeypatch, bundle)
    prompt = prompts[0]

    assert re.search(r"import semver\b", prompt), (
        "prompt does not state 'import semver'"
    )
    for p in prompts:
        assert "import comp_semver" not in p