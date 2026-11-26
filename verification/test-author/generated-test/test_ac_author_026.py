# hotdocs-criterion: sha256:4d6d74a6a61b227b24b25e97dd8eaf01733b1d1ca560ba7dfbc67007e58d798f
import re

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

GOOD_TEST = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(repr(module_name) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + GOOD_TEST
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def run_author(tmp_path, monkeypatch, name, bundle):
    repo_root = tmp_path / name
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    write_probe_stand_in(repo_root, tmp_path / (name + "-probe.log"))
    prompts = []
    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=make_backend(prompts)
    )
    return prompts, result


def base_bundle(component_id, criterion_id, covers):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "Given an input\nWhen it runs\nThen it works",
        "requirement_text": "The thing MUST work.",
        "interface": "do_thing(x: str) -> str",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_module_names_replace_derived_import(tmp_path, monkeypatch):
    bundle = base_bundle("capabilities/P-SLUGS", "AC-P-SLUGS-001", "R-P-SLUGS-001")
    bundle["module_names"] = ["slugify", "url_tools"]

    prompts, _result = run_author(tmp_path, monkeypatch, "caps", bundle)

    assert prompts, "the model backend was never called"
    for prompt in prompts:
        assert "import slugify" in prompt
        assert "import url_tools" in prompt
        assert "import capabilities" not in prompt


def test_empty_module_names_uses_derived_import(tmp_path, monkeypatch):
    bundle = base_bundle("comp-semver", "AC-SEMVER-001", "R-SEMVER-001")
    bundle["module_names"] = []

    prompts, _result = run_author(tmp_path, monkeypatch, "semver", bundle)

    assert prompts, "the model backend was never called"
    for prompt in prompts:
        assert "import semver" in prompt