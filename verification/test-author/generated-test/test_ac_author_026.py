# hotdocs-criterion: sha256:3208278817fae6a9a2df33d980c1183400c19672b23f51060cc452f733d8edd9
import re

import test_author


BEGIN_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

REPLY_TEST = "def test_placeholder():\n    assert 1 + 1 == 2\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plant_probe(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
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
        "    with open(" + repr(str(log_path)) + ", 'a') as handle:\n"
        "        handle.write(repr(module_name) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source)


def make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(BEGIN_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + REPLY_TEST
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def run_author(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    plant_probe(repo_root, tmp_path / "probe_calls.log")
    prompts = []
    try:
        test_author.author_test(
            bundle, "mock", 0, repo_root=repo_root, llm_backend=make_backend(prompts)
        )
    except Exception:
        # The criterion concerns only the prompt the model receives.
        pass
    assert prompts, "author_test never called the model backend"
    return prompts


def test_module_names_replace_derived_name(tmp_path, monkeypatch):
    bundle = {
        "component_id": "capabilities/P-SLUGS",
        "criterion_id": "AC-SLUGS-001",
        "covers": "R-SLUGS-001",
        "criterion_text": "Given a title\nWhen slugified\nThen the slug is lowercase",
        "requirement_text": "R-SLUGS-001 - slugs are lowercase.",
        "interface": "slugify(text: str) -> str\nurl_tools.join(a: str, b: str) -> str",
        "glossary": "",
        "dependency_interfaces": {},
        "module_names": ["slugify", "url_tools"],
    }
    prompts = run_author(tmp_path, monkeypatch, bundle)
    for prompt in prompts:
        assert "import slugify" in prompt
        assert "import url_tools" in prompt
        assert "import capabilities" not in prompt


def test_empty_module_names_uses_derived_name(tmp_path, monkeypatch):
    bundle = {
        "component_id": "comp-semver",
        "criterion_id": "AC-SEMVER-001",
        "covers": "R-SEMVER-001",
        "criterion_text": "Given 1.2.3\nWhen parsed\nThen major is 1",
        "requirement_text": "R-SEMVER-001 - versions parse into parts.",
        "interface": "parse(text: str) -> Version",
        "glossary": "",
        "dependency_interfaces": {},
        "module_names": [],
    }
    prompts = run_author(tmp_path, monkeypatch, bundle)
    for prompt in prompts:
        assert "import semver" in prompt