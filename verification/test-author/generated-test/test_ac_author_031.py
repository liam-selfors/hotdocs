# hotdocs-criterion: sha256:ba3e02c0266a4a72fff317e05b5f578c5a0ffd6d1f5b4bc4e4eb6d1d422aa8c1
import re
from pathlib import Path

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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, "
        "interpreter=None, assets=None, drivers=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock(prompts):
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


def make_bundle(testing):
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, when made, then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - The maker MUST make widgets.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": testing,
    }


def run_author(tmp_path, monkeypatch, name, testing):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-probe.log")
    write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    prompts = []
    result = test_author.author_test(
        make_bundle(testing),
        "mock",
        repo_root=repo_root,
        llm_backend=make_mock(prompts),
    )
    return result, prompts, log_path


def test_testing_text_included_under_test_spec_heading(tmp_path, monkeypatch):
    testing = "Write fixtures with write_fixture(repo_root)."
    result, prompts, log_path = run_author(tmp_path, monkeypatch, "with-testing", testing)

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1
    first = prompts[0]
    assert "## Test spec" in first.splitlines()
    assert "Write fixtures with write_fixture(repo_root)." in first


def test_empty_testing_adds_no_test_spec_heading(tmp_path, monkeypatch):
    result, prompts, log_path = run_author(tmp_path, monkeypatch, "without-testing", "")

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1
    first = prompts[0]
    assert "## Test spec" not in first