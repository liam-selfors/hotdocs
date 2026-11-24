# hotdocs-criterion: sha256:f2ae21b73b7f36732e212dc7f375318cf752b09f8dd4937570ab837dbb3a4c33
import re
from pathlib import Path, PurePosixPath

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    base = repo_root / "gen" / "test-probe"
    base.mkdir(parents=True, exist_ok=True)
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
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (base / "test_probe.py").write_text(source, encoding="utf-8")


def _snapshot(directory):
    if not directory.exists():
        return set()
    return {
        p.relative_to(directory).as_posix()
        for p in directory.rglob("*")
        if p.is_file()
    }


def test_written_path_is_under_verification_generated_test(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    gen_before = _snapshot(repo_root / "gen")

    test_body = "def test_something():\n    assert True\n"

    def backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_body
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-006",
        "covers": "R-WIDGET-MAKER-006",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-006 - widgets MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert field(result, "model_call_error") is None
    assert probe_log.is_file()
    assert probe_log.read_text(encoding="utf-8").count("probe\n") >= 1

    file_entry = field(result, "file")
    assert file_entry is not None
    rel = field(file_entry, "path")
    rel_path = PurePosixPath(str(rel).replace("\\", "/"))

    expected = PurePosixPath(
        "verification/widget-maker/generated-test/test_ac_widget_maker_006.py"
    )
    assert rel_path == expected

    # Under verification/<component>/generated-test/, directly.
    assert rel_path.parts[:3] == ("verification", "widget-maker", "generated-test")
    assert len(rel_path.parts) == 4
    # Not under gen/<component>/ (nor gen/ at all).
    assert rel_path.parts[0] != "gen"
    # Not under criterion-compiler's own output directory.
    assert "compiled" not in rel_path.parts

    written = repo_root / Path(*rel_path.parts)
    assert written.is_file()
    resolved = written.resolve()
    assert resolved.is_relative_to(
        (repo_root / "verification" / "widget-maker" / "generated-test").resolve()
    )
    assert not resolved.is_relative_to((repo_root / "gen").resolve())
    assert not resolved.is_relative_to(
        (repo_root / "verification" / "widget-maker" / "compiled").resolve()
    )

    # Exactly that one file was written under verification/.
    assert _snapshot(repo_root / "verification") == {
        "widget-maker/generated-test/test_ac_widget_maker_006.py"
    }
    # Nothing was added under gen/ (in particular, not gen/widget-maker/).
    assert _snapshot(repo_root / "gen") == gen_before
    assert not (repo_root / "gen" / "widget-maker").exists()
    assert not (repo_root / "verification" / "widget-maker" / "compiled").exists()