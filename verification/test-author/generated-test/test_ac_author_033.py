# hotdocs-criterion: sha256:6bdd2d95a7b2ec40679c05981413bf16d27ff4cafb29d83537c32d6c949ab9e9
import re

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

EXPECTED_MESSAGE = (
    "model reply held no matching BEGIN/END FILE markers; "
    "reply began: 'no markers here'"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - widgets MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
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
        "            'ok': self.ok,\n"
        "            'findings': [dict(f) for f in self.findings],\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None, **kwargs):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(test_source) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock(replies):
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        index = len(prompts) - 1
        reply = replies(index, nonce)
        return {
            "text": reply,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend, prompts


def verification_files(repo_root):
    vdir = repo_root / "verification"
    if not vdir.exists():
        return []
    return [p for p in vdir.rglob("*") if p.is_file()]


def test_repair_after_missing_markers_succeeds(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_success"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_success.log"
    plant_probe_stand_in(repo_root, log_path)

    def replies(index, nonce):
        if index == 0:
            return "no markers here"
        return (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import x\n"
            "-----END FILE " + nonce + "-----"
        )

    backend, prompts = make_mock(replies)

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )

    assert field(result, "model_call_error") is None
    assert field(result, "repair_attempts") == 1
    assert len(prompts) >= 2

    n1 = re.findall(NONCE_RE, prompts[0])[-1]
    expected_line = (
        "Your reply held no BEGIN FILE / END FILE marker pair with the nonce "
        + n1
        + "."
    )
    assert expected_line in prompts[1].splitlines()


def test_repairs_exhausted_without_markers(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_failure"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_failure.log"
    plant_probe_stand_in(repo_root, log_path)

    def replies(index, nonce):
        return "no markers here"

    backend, prompts = make_mock(replies)

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "missing_file_markers"
    assert field(error, "message") == EXPECTED_MESSAGE
    assert field(result, "repair_attempts") == 2
    assert field(result, "file") is None
    assert verification_files(repo_root) == []