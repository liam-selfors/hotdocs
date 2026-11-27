# hotdocs-criterion: sha256:2b2dc6c835943bbf5b052b510dac051cb2a835d04e11750f277bae6f52c28541
import re

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

GOOD_TEST = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plant_probe_stand_in(repo_root, log_path):
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
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(repr(module_name) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = NONCE_RE.findall(prompt)[-1]
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


def base_bundle(component_id, criterion_id, covers):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "Given something\nWhen it happens\nThen it is so",
        "requirement_text": "The thing MUST be so.",
        "interface": "do_it() -> None",
        "glossary": "",
        "dependency_interfaces": {},
    }


def run_author(tmp_path, monkeypatch, name, bundle):
    repo_root = tmp_path / name
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / (name + "-probe.log")
    plant_probe_stand_in(repo_root, log_path)
    prompts = []
    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=make_backend(prompts)
    )
    return result, prompts


def test_module_names_replace_derived_name(tmp_path, monkeypatch):
    bundle = base_bundle(
        "capabilities/P-SLUGS", "AC-SLUGS-001", "R-SLUGS-001"
    )
    bundle["module_names"] = ["slugify", "url_tools"]

    result, prompts = run_author(tmp_path, monkeypatch, "scenario1", bundle)

    assert prompts, "author_test never called the model backend"
    assert field(result, "model_call_error") is None
    for prompt in prompts:
        assert "import slugify" in prompt
        assert "import url_tools" in prompt
        assert "import capabilities" not in prompt


def test_empty_module_names_uses_derived_name(tmp_path, monkeypatch):
    bundle = base_bundle("comp-semver", "AC-SEMVER-001", "R-SEMVER-001")
    bundle["module_names"] = []

    result, prompts = run_author(tmp_path, monkeypatch, "scenario2", bundle)

    assert prompts, "author_test never called the model backend"
    assert field(result, "model_call_error") is None
    for prompt in prompts:
        assert "import semver" in prompt