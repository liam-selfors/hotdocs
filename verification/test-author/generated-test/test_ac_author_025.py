# hotdocs-criterion: sha256:e3e24324b477363a859498c64a754d19de3181b99de4bf38d2da344f24421ee8
import re

import pytest

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

ACCEPTED_TEST = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": list(self.findings),\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(LOG, " + repr("a") + ") as handle:\n"
        "        handle.write(" + repr("probe\n") + ")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + ACCEPTED_TEST
            + "\n-----END FILE " + nonce + "-----"
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
        "criterion_text": "Given a value\nWhen the function runs\nThen it returns a result",
        "requirement_text": "The function MUST return a result.",
        "interface": "run(value) -> str",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _collect_prompts(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    prompts = []
    test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=_make_backend(prompts)
    )
    return prompts


def test_hyphenated_component_id_yields_underscored_import(tmp_path, monkeypatch):
    bundle = _bundle("comp-foo-bar", "AC-FOO-BAR-001", "R-FOO-BAR-001")
    prompts = _collect_prompts(tmp_path, monkeypatch, bundle)

    assert prompts, "author_test never called the model backend"
    for prompt in prompts:
        assert "import foo_bar" in prompt
        assert "import comp_foo_bar" not in prompt


def test_single_word_component_id_yields_plain_import(tmp_path, monkeypatch):
    bundle = _bundle("comp-semver", "AC-SEMVER-001", "R-SEMVER-001")
    prompts = _collect_prompts(tmp_path, monkeypatch, bundle)

    assert prompts, "author_test never called the model backend"
    for prompt in prompts:
        assert "import semver" in prompt
        assert "import comp_semver" not in prompt