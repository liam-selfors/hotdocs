# hotdocs-criterion: sha256:ff586f8c2ef1281c46d7176f6153d6b2f2a2a0d9302acecbd51dff3787967184
import dataclasses
import json
import logging
import os
import re
import secrets

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


TEST_BODY = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() is not None\n"
)


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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _mock_backend(prompt, model, **params):
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


def _result_texts(result):
    texts = [repr(result), str(result)]
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        texts.append(json.dumps(dataclasses.asdict(result), default=str))
    elif isinstance(result, dict):
        texts.append(json.dumps(result, default=str))
    for name in (
        "component_id",
        "criterion_id",
        "model",
        "seed",
        "prompt_version",
        "cache_hit",
        "file",
        "model_call_error",
        "repair_attempts",
        "probe_findings",
    ):
        texts.append(repr(field(result, name)))
    return texts


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, capsys, caplog):
    sentinel = "sk-ant-hotdocs-SENTINEL-" + secrets.token_hex(16)
    monkeypatch.setenv("ANTHROPIC_API_KEY", sentinel)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", sentinel)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    caplog.set_level(logging.DEBUG)

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=_mock_backend
    )

    # The call was successful.
    assert field(result, "model_call_error") is None
    file_value = field(result, "file")
    assert file_value is not None
    assert body(field(file_value, "content")) == TEST_BODY
    assert probe_log.is_file()
    assert probe_log.read_text(encoding="utf-8").count("probe\n") >= 1

    # The key's value appears nowhere in the returned result.
    for text in _result_texts(result):
        assert sentinel not in text

    # Nor in captured stdout/stderr or Python logging output.
    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err
    assert sentinel not in caplog.text
    for record in caplog.records:
        assert sentinel not in record.getMessage()

    # Nor in any file written under repo_root: the written test, the cache
    # entry, and llm-endpoint's call logs under .hotdocs/calls/.
    needle = sentinel.encode("utf-8")
    checked = 0
    for dirpath, _dirnames, filenames in os.walk(tmp_path):
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                data = fh.read()
            assert needle not in data, "API key value found in " + path
            checked += 1
    assert checked > 0

    written = repo_root / field(file_value, "path")
    assert written.is_file()
    assert sentinel not in written.read_text(encoding="utf-8")