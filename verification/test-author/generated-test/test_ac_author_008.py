# hotdocs-criterion: sha256:27af80656613411fa8ce0c572e3ba4509b9f2c7d0f6ed7114cddc33fbbfc58a4
import dataclasses
import json
import logging
import re
import secrets

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TEST_BODY = "def test_placeholder():\n    assert True\n"


def _write_probe_stand_in(repo_root, log_path):
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
        "        return dict(ok=self.ok, findings=list(self.findings),\n"
        "                    tests_run=self.tests_run, tests_reached=self.tests_reached)\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _make_backend():
    def backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + TEST_BODY
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _result_texts(result):
    texts = [repr(result), str(result)]
    if dataclasses.is_dataclass(result):
        texts.append(json.dumps(dataclasses.asdict(result), default=str))
    elif isinstance(result, dict):
        texts.append(json.dumps(result, default=str))
    else:
        texts.append(repr(vars(result)) if hasattr(result, "__dict__") else "")
    return texts


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, capsys, caplog):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    secret = "sk-ant-api03-HOTDOCSSENTINEL" + secrets.token_hex(16)
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", secret)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 widgets MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    caplog.set_level(logging.DEBUG)
    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=_make_backend()
    )

    # The call was successful.
    assert field(result, "model_call_error") is None
    file_entry = field(result, "file")
    assert file_entry is not None
    assert probe_log.is_file()

    # The result, in every rendering, holds no trace of the key.
    for text in _result_texts(result):
        assert secret not in text

    # Captured stdout/stderr and Python logging hold no trace of the key.
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    assert secret not in caplog.text
    for record in caplog.records:
        assert secret not in record.getMessage()

    # Every file under repo_root (call logs under .hotdocs/calls/, the written
    # test, any provenance) holds no trace of the key.
    secret_bytes = secret.encode("utf-8")
    checked = 0
    for path in repo_root.rglob("*"):
        if path.is_file():
            checked += 1
            assert secret_bytes not in path.read_bytes(), str(path)
    assert checked > 0