# hotdocs-criterion: sha256:66137201e6331035d1f11ba67837a7a55178a3ea3f63b6eca576b1167e151c59
import dataclasses
import json
import logging
import os
import re
import secrets
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


TEST_BODY = "import widget_maker\n\n\ndef test_it():\n    assert widget_maker.make() is not None\n"


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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe called\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend():
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


def result_texts(result):
    texts = [repr(result), str(result)]
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        as_dict = dataclasses.asdict(result)
    elif isinstance(result, dict):
        as_dict = result
    else:
        as_dict = {
            name: getattr(result, name)
            for name in (
                "component_id", "criterion_id", "model", "seed",
                "prompt_version", "cache_hit", "file", "model_call_error",
                "repair_attempts", "probe_findings",
            )
        }
    texts.append(json.dumps(as_dict, default=str, ensure_ascii=False))
    texts.append(repr(as_dict))
    return texts


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, capsys, caplog):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    secret = "sk-ant-api03-HOTDOCSSENTINEL" + secrets.token_hex(24)
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", secret)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
        "module_names": ["widget_maker"],
    }

    caplog.set_level(logging.DEBUG)
    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=make_backend()
    )

    # The call succeeded.
    assert field(result, "model_call_error") is None
    file_entry = field(result, "file")
    assert file_entry is not None
    assert body(file_entry["content"]) == TEST_BODY
    assert field(result, "model") == "mock"
    assert probe_log.is_file()
    assert probe_log.read_text(encoding="utf-8").count("probe called") >= 1

    # The result never holds the key.
    for text in result_texts(result):
        assert secret not in text

    # Nothing written under repo_root (written test, call logs, anything) holds it.
    secret_bytes = secret.encode("utf-8")
    checked = 0
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for name in filenames:
            path = Path(dirpath) / name
            data = path.read_bytes()
            checked += 1
            assert secret_bytes not in data, "API key found in " + str(path)
    assert checked >= 1

    written = repo_root / file_entry["path"]
    assert written.is_file()
    assert secret not in written.read_text(encoding="utf-8")

    # Neither stdout/stderr nor Python logging output holds it.
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    assert secret not in caplog.text
    for record in caplog.records:
        assert secret not in record.getMessage()