# hotdocs-criterion: sha256:7e47bd97450e6c332a2e522ef9bb5c652db497031548f31c419562e577d3c870
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    src = (
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write('call\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(src)


def _make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        n = nonces[-1]
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

    return backend


def _bundle(component_id, criterion_id, module_names):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": criterion_id.replace("AC-", "R-", 1),
        "criterion_text": "Given something\nWhen something happens\nThen a result",
        "requirement_text": "The component MUST do something.",
        "interface": "",
        "glossary": "",
        "dependency_interfaces": {},
        "module_names": module_names,
    }


def _run(repo_root, monkeypatch, bundle):
    repo_root.mkdir(parents=True, exist_ok=True)
    log_path = repo_root.parent / (repo_root.name + "-probe.log")
    _write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    prompts = []
    result = test_author.author_test(
        bundle,
        "mock",
        0,
        repo_root=repo_root,
        llm_backend=_make_backend(prompts),
    )
    assert field(result, "model_call_error") is None
    assert prompts, "the mock backend was never called"
    return prompts


def test_module_names_replace_derived_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo-capability"
    bundle = _bundle(
        "capabilities/P-SLUGS", "AC-P-SLUGS-001", ["slugify", "url_tools"]
    )
    prompts = _run(repo_root, monkeypatch, bundle)
    for prompt in prompts:
        assert "import slugify" in prompt
        assert "import url_tools" in prompt
        assert "import capabilities" not in prompt


def test_empty_module_names_uses_derived_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo-semver"
    bundle = _bundle("comp-semver", "AC-SEMVER-001", [])
    prompts = _run(repo_root, monkeypatch, bundle)
    for prompt in prompts:
        assert "import semver" in prompt