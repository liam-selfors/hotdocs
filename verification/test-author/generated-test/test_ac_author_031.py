# hotdocs-criterion: sha256:6c91e82c22efc2215d35e46f54371a16f5f9f6a5a6f19586c29856679bc80455
import re

import test_author


TESTING_TEXT = "Write fixtures with write_fixture(repo_root)."

REPLY_FILE = (
    "import test_author\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert test_author is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(testing):
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - The maker MUST make a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": testing,
    }


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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + REPLY_FILE
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def run_author(tmp_path, monkeypatch, name, testing):
    repo_root = tmp_path / name
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / (name + "-probe.log")
    plant_probe_stand_in(repo_root, log_path)
    prompts = []
    result = test_author.author_test(
        make_bundle(testing),
        "mock",
        repo_root=repo_root,
        llm_backend=make_mock_backend(prompts),
    )
    return result, prompts


def test_nonempty_testing_is_included_under_test_spec_heading(tmp_path, monkeypatch):
    result, prompts = run_author(tmp_path, monkeypatch, "with-testing", TESTING_TEXT)

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1
    first = prompts[0]
    assert "## Test spec" in first.splitlines()
    assert TESTING_TEXT in first


def test_empty_testing_adds_no_test_spec_heading(tmp_path, monkeypatch):
    result, prompts = run_author(tmp_path, monkeypatch, "without-testing", "")

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1
    first = prompts[0]
    assert "## Test spec" not in first