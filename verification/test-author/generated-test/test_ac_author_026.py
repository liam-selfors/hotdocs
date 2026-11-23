# hotdocs-criterion: sha256:7f18bb73bac4cf00d4c24a1617b28593d51c43949160457ddafcba132765481f
import re

import test_author


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
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return _Report()\n"
)

REPLY_BODY = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _plant_probe(repo_root):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "test_probe.py").write_text(PROBE_STAND_IN, encoding="utf-8")


def _make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + REPLY_BODY
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _run(tmp_path, monkeypatch, name, bundle):
    repo_root = tmp_path / name
    repo_root.mkdir()
    _plant_probe(repo_root)
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    prompts = []
    test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=_make_backend(prompts)
    )
    assert prompts, "the mock model was never called, so no prompt was observed"
    return prompts


def test_module_names_replace_derived_import(tmp_path, monkeypatch):
    bundle = {
        "component_id": "capabilities/P-SLUGS",
        "criterion_id": "AC-SLUGS-001",
        "covers": "R-SLUGS-001",
        "criterion_text": "Given a title When it is slugged Then the slug is lowercase",
        "requirement_text": "R-SLUGS-001: slugs are lowercase.",
        "interface": "slugify(text: str) -> str\njoin_url(base: str, slug: str) -> str",
        "glossary": "",
        "dependency_interfaces": {},
        "module_names": ["slugify", "url_tools"],
    }
    prompts = _run(tmp_path, monkeypatch, "scenario_one", bundle)
    for prompt in prompts:
        assert "import slugify" in prompt
        assert "import url_tools" in prompt
        assert "import capabilities" not in prompt


def test_empty_module_names_uses_derived_name(tmp_path, monkeypatch):
    bundle = {
        "component_id": "comp-semver",
        "criterion_id": "AC-SEMVER-001",
        "covers": "R-SEMVER-001",
        "criterion_text": "Given two versions When compared Then the higher one wins",
        "requirement_text": "R-SEMVER-001: versions compare numerically.",
        "interface": "compare(a: str, b: str) -> int",
        "glossary": "",
        "dependency_interfaces": {},
        "module_names": [],
    }
    prompts = _run(tmp_path, monkeypatch, "scenario_two", bundle)
    for prompt in prompts:
        assert "import semver" in prompt