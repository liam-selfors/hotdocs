# hotdocs-criterion: sha256:00452ab04be25a74137d0d892a17c9e4c62d1467f9d4d5c0b03c20e30dcbcead
import re

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

GOOD_TEST = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
    target_dir = repo_root / "gen" / "test-probe"
    target_dir.mkdir(parents=True, exist_ok=True)
    source = (
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(repr(module_name) + '\\n')\n"
        "    return _Report()\n"
    )
    (target_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_bundle(component_id, criterion_id, covers):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "Given an input\nWhen the function runs\nThen it returns a value",
        "requirement_text": "The function MUST return a value.",
        "interface": "# Library\n\n```\nrun(x: str) -> str\n```\n",
        "glossary": "",
        "dependency_interfaces": {},
    }


def capture_prompts(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)

    prompts = []

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

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=backend
    )
    assert prompts, "author_test made no model call"
    return prompts, result


def test_hyphenated_component_id_yields_underscored_import(tmp_path, monkeypatch):
    bundle = make_bundle("comp-foo-bar", "AC-FOO-BAR-001", "R-FOO-BAR-001")
    prompts, _result = capture_prompts(tmp_path, monkeypatch, bundle)

    first = prompts[0]
    assert "import foo_bar" in first
    for prompt in prompts:
        assert "import comp_foo_bar" not in prompt
        assert "import comp-foo-bar" not in prompt


def test_single_word_component_id_yields_plain_import(tmp_path, monkeypatch):
    bundle = make_bundle("comp-semver", "AC-SEMVER-001", "R-SEMVER-001")
    prompts, _result = capture_prompts(tmp_path, monkeypatch, bundle)

    first = prompts[0]
    assert "import semver" in first
    for prompt in prompts:
        assert "import comp_semver" not in prompt
        assert "import comp-semver" not in prompt