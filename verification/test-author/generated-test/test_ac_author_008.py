# hotdocs-criterion: sha256:c5de1caec6028adb97ff890fdf0a9cff5213193e42e2834a7305ca37c50e0639
# AC-AUTHOR-008: a successful author_test call never exposes
# VAR-ANTHROPIC-API-KEY's value in its TestAuthoringResult or any logs.
import dataclasses
import json
import logging
import os
import re
import secrets

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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run,\n"
        "                'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as f:\n"
        "        f.write('probe called\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(src, encoding="utf-8")


def _mock_backend(prompt, model, **params):
    nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
    body = "def test_placeholder():\n    assert True\n"
    text = (
        "-----BEGIN FILE " + nonce + "-----\n"
        + body
        + "\n-----END FILE " + nonce + "-----"
    )
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _result_as_text(result):
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        data = dataclasses.asdict(result)
    elif isinstance(result, dict):
        data = result
    else:
        data = dict(vars(result))
    return json.dumps(data, default=str) + "\n" + repr(result) + "\n" + str(result)


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, capsys, caplog):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)
    monkeypatch.chdir(repo_root)

    secret = "sk-ant-api03-HOTDOCSSECRET" + secrets.token_hex(16)
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", secret)

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
        bundle, "mock", 0, repo_root=repo_root, llm_backend=_mock_backend
    )

    # The call was successful.
    assert field(result, "model_call_error") is None
    file_entry = field(result, "file")
    assert file_entry is not None
    assert probe_log.is_file()

    # The result itself never holds the key.
    result_text = _result_as_text(result)
    assert secret not in result_text
    assert secret not in field(file_entry, "content")
    assert secret not in field(file_entry, "path")
    assert secret not in field(result, "model")

    # No file written anywhere under repo_root (written test, call logs
    # under .hotdocs/calls/, anything else) holds the key.
    secret_bytes = secret.encode("utf-8")
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as f:
                data = f.read()
            assert secret_bytes not in data, path
            assert secret not in path

    # Nothing printed or logged in-process holds the key.
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    assert secret not in caplog.text
    for record in caplog.records:
        assert secret not in record.getMessage()