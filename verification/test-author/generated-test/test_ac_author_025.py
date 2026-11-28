# hotdocs-criterion: sha256:7e719de4670a861881748ab5764c3c8c3fb563b96a3db4f58639774e0790879d
import re

import pytest

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PROBE_SOURCE_HEAD = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 1\n"
    "        self.tests_reached = 1\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {\n"
    "            'ok': self.ok,\n"
    "            'findings': list(self.findings),\n"
    "            'tests_run': self.tests_run,\n"
    "            'tests_reached': self.tests_reached,\n"
    "        }\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
)


def plant_probe(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        PROBE_SOURCE_HEAD
        + "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        + "        fh.write('probe\\n')\n"
        + "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_bundle(component_id, criterion_id, covers):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "Given an input\nWhen the function runs\nThen it returns a value",
        "requirement_text": "The function MUST return a value.",
        "interface": "# Library\n\n```\nrun(x: int) -> int\n```\n",
        "glossary": "",
        "dependency_interfaces": {},
    }


def run_author(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    probe_log = tmp_path / "probe.log"
    plant_probe(repo_root, probe_log)

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + "def test_placeholder():\n    assert True\n"
            + "\n-----END FILE " + nonce + "-----"
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
    assert prompts, "author_test made no model call"
    assert field(result, "model_call_error") is None
    return prompts


def test_hyphenated_component_id_imports_underscored_slug(tmp_path, monkeypatch):
    bundle = make_bundle("comp-foo-bar", "AC-FOO-BAR-001", "R-FOO-BAR-001")
    prompts = run_author(tmp_path, monkeypatch, bundle)
    for prompt in prompts:
        assert "import foo_bar" in prompt
        assert "import comp_foo_bar" not in prompt
        assert "import comp-foo-bar" not in prompt


def test_single_word_component_id_imports_slug(tmp_path, monkeypatch):
    bundle = make_bundle("comp-semver", "AC-SEMVER-001", "R-SEMVER-001")
    prompts = run_author(tmp_path, monkeypatch, bundle)
    for prompt in prompts:
        assert "import semver" in prompt
        assert "import comp_semver" not in prompt