# hotdocs-criterion: sha256:7f18bb73bac4cf00d4c24a1617b28593d51c43949160457ddafcba132765481f
import re

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

TEST_BODY = "def test_ok():\n    assert True\n"


def _make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        n = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = "-----BEGIN FILE " + n + "-----\n" + TEST_BODY + "\n-----END FILE " + n + "-----"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def _setup_repo(repo_root, monkeypatch):
    repo_root.mkdir(parents=True, exist_ok=True)
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "test_probe.py").write_text(PROBE_SOURCE, encoding="utf-8")
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def _bundle(component_id, criterion_id, module_names):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": criterion_id.replace("AC-", "R-", 1),
        "criterion_text": "Given an input\nWhen it is processed\nThen the output is correct",
        "requirement_text": "The component MUST process input correctly.",
        "interface": "process(text: str) -> str",
        "glossary": "",
        "dependency_interfaces": {},
        "module_names": module_names,
    }


def test_module_names_replace_derived_import(tmp_path, monkeypatch):
    repo_root = tmp_path / "scenario_a"
    _setup_repo(repo_root, monkeypatch)
    prompts = []
    bundle = _bundle("capabilities/P-SLUGS", "AC-SLUGS-001", ["slugify", "url_tools"])
    test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=_make_backend(prompts)
    )
    assert prompts, "author_test never called the model backend"
    for prompt in prompts:
        assert "import slugify" in prompt
        assert "import url_tools" in prompt
        assert "import capabilities" not in prompt


def test_empty_module_names_uses_derived_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "scenario_b"
    _setup_repo(repo_root, monkeypatch)
    prompts = []
    bundle = _bundle("comp-semver", "AC-SEMVER-001", [])
    test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=_make_backend(prompts)
    )
    assert prompts, "author_test never called the model backend"
    for prompt in prompts:
        assert "import semver" in prompt