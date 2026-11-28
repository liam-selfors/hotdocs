# hotdocs-criterion: sha256:21f0df30055b459ed60d5bd03dd876896bec125fe013b593e49890046d005ee4
import re
from pathlib import Path

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(repr(test_source) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def last_nonce(prompt):
    return NONCE_RE.findall(prompt)[-1]


def make_mock(replies_fn, prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        n = last_nonce(prompt)
        text = replies_fn(len(prompts), n)
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def verification_files(repo_root):
    vdir = repo_root / "verification"
    if not vdir.exists():
        return []
    return [p for p in vdir.rglob("*") if p.is_file()]


def test_one_repair_after_missing_markers(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_one"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    plant_probe(repo_root, tmp_path / "probe_log_one.txt")

    prompts = []

    def replies(call_no, n):
        if call_no == 1:
            return "no markers here"
        return "-----BEGIN FILE " + n + "-----\nimport x\n-----END FILE " + n + "-----"

    backend = make_mock(replies, prompts)
    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )

    assert field(result, "model_call_error") is None
    assert field(result, "repair_attempts") == 1
    assert len(prompts) >= 2

    n1 = last_nonce(prompts[0])
    expected_line = (
        "Your reply held no BEGIN FILE / END FILE marker pair with the nonce "
        + n1
        + "."
    )
    assert expected_line in prompts[1].splitlines()


def test_missing_markers_every_call(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_two"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    plant_probe(repo_root, tmp_path / "probe_log_two.txt")

    prompts = []

    def replies(call_no, n):
        return "no markers here"

    backend = make_mock(replies, prompts)
    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )

    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "missing_file_markers"
    assert field(err, "message") == (
        "model reply held no matching BEGIN/END FILE markers; "
        "reply began: 'no markers here'"
    )
    assert field(result, "repair_attempts") == 2
    assert field(result, "file") is None
    assert verification_files(repo_root) == []