# hotdocs-criterion: sha256:80e788d947c656100254ac0b8d1c26d224ca46e617820ad921773cce8c79be5f
import dataclasses
import json
import logging
import re
import secrets

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PROBE_SOURCE_TEMPLATE_HEAD = (
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
)


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        PROBE_SOURCE_TEMPLATE_HEAD
        + "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "\n"
        + "\n"
        + "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        + "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        + "        fh.write('probe-called\\n')\n"
        + "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 — a widget MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def all_text_under(root):
    chunks = []
    for path in root.rglob("*"):
        if path.is_file():
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
            chunks.append(str(path))
    return "\n".join(chunks)


def result_text(result):
    parts = [repr(result), str(result)]
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        data = dataclasses.asdict(result)
    elif isinstance(result, dict):
        data = result
    else:
        data = None
    if data is not None:
        parts.append(json.dumps(data, default=str, ensure_ascii=False))
    for name in ("component_id", "criterion_id", "model", "seed", "prompt_version",
                 "cache_hit", "file", "model_call_error", "repair_attempts",
                 "probe_findings"):
        try:
            parts.append(json.dumps(field(result, name), default=str, ensure_ascii=False))
        except (KeyError, AttributeError):
            pass
    return "\n".join(parts)


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, caplog, capfd):
    secret = "sk-ant-hotdocs-sentinel-" + secrets.token_hex(16)
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", secret)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    mock_log = tmp_path / "mock_calls.log"
    test_body = "def test_widget():\n    assert True"

    def mock_backend(prompt, model, **params):
        with open(mock_log, "a", encoding="utf-8") as fh:
            fh.write("mock-called\n")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = ("-----BEGIN FILE " + nonce + "-----\n" + test_body
                + "\n-----END FILE " + nonce + "-----")
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    caplog.set_level(logging.DEBUG)

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    # The call was successful.
    assert field(result, "model_call_error") is None
    file_entry = field(result, "file")
    assert file_entry is not None
    assert mock_log.read_text(encoding="utf-8").count("mock-called") >= 1
    assert probe_log.read_text(encoding="utf-8").count("probe-called") >= 1

    # Only the model identifier actually used is recorded.
    assert field(result, "model") == "mock"

    # The key appears nowhere in the returned result.
    assert secret not in result_text(result)

    # Nor anywhere in the files written or logged under repo_root
    # (including llm-endpoint's .hotdocs/calls/ logs and the written test).
    assert secret not in all_text_under(repo_root)

    # Nor in any emitted log records or process output.
    for record in caplog.records:
        assert secret not in record.getMessage()
        assert secret not in repr(record.__dict__)
    assert secret not in caplog.text
    captured = capfd.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err