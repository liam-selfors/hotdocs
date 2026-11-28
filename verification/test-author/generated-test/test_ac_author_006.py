# hotdocs-criterion: sha256:40b13f851383ca67910b975682409fda39b9b32ef05fa3e4d25fd1db6ab915e5
import os
import re
from pathlib import Path

import test_author


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
CRITERION_ID = "AC-WIDGET-MAKER-001"
EXPECTED_FILENAME = "test_ac_widget_maker_001.py"

TEST_BODY = "def test_placeholder():\n    assert 1 + 1 == 2\n"

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - A widget MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock_backend():
    def backend(prompt, model, **params):
        nonce = NONCE_RE.findall(prompt)[-1]
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


def snapshot(root):
    result = {}
    if not root.exists():
        return result
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            result[p.relative_to(root).as_posix()] = p.read_bytes()
    return result


def is_under(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def test_written_file_is_under_generated_test_dir_only(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)

    # Plant criterion-compiler's own output for the same criterion, so any
    # write there would be observable.
    compiled_dir = repo_root / "verification" / SLUG / "compiled"
    compiled_dir.mkdir(parents=True)
    compiled_sentinel = "# criterion-compiler output, must stay untouched\n"
    (compiled_dir / EXPECTED_FILENAME).write_text(compiled_sentinel, encoding="utf-8")

    gen_before = snapshot(repo_root / "gen")
    compiled_before = snapshot(compiled_dir)

    result = test_author.author_test(
        make_bundle(),
        "mock",
        0,
        repo_root=repo_root,
        llm_backend=make_mock_backend(),
    )

    # The call was successful.
    assert field(result, "model_call_error") is None
    assert log_path.is_file(), "the test-probe stand-in was never called"
    file_entry = field(result, "file")
    assert file_entry is not None

    rel_path_str = field(file_entry, "path")
    rel_path = Path(rel_path_str)
    assert not rel_path.is_absolute()
    assert rel_path.as_posix() == (
        "verification/" + SLUG + "/generated-test/" + EXPECTED_FILENAME
    )

    written = (repo_root / rel_path).resolve()
    assert written.is_file()

    root_resolved = repo_root.resolve()
    generated_test_dir = (root_resolved / "verification" / SLUG / "generated-test")
    gen_component_dir = root_resolved / "gen" / SLUG
    gen_dir = root_resolved / "gen"
    compiled_resolved = compiled_dir.resolve()

    # Directly under verification/<slug>/generated-test/, no nesting.
    assert written.parent == generated_test_dir
    assert written.name == EXPECTED_FILENAME
    assert is_under(written, generated_test_dir)

    # Never under gen/<component>/ (nor gen/ at all) nor criterion-compiler's dir.
    assert not is_under(written, gen_component_dir)
    assert not is_under(written, gen_dir)
    assert not is_under(written, compiled_resolved)

    # Nothing written or modified under gen/ or criterion-compiler's output dir.
    assert snapshot(repo_root / "gen") == gen_before
    assert not (repo_root / "gen" / SLUG).exists()
    assert snapshot(compiled_dir) == compiled_before
    assert (compiled_dir / EXPECTED_FILENAME).read_text(encoding="utf-8") == compiled_sentinel

    # The only new file under verification/ is the generated-test file.
    verification_files = snapshot(repo_root / "verification")
    new_files = sorted(
        k for k in verification_files if k not in {
            SLUG + "/compiled/" + EXPECTED_FILENAME,
        }
    )
    assert new_files == [SLUG + "/generated-test/" + EXPECTED_FILENAME]

    # The written file is the one the result reports.
    assert written.read_text(encoding="utf-8") == field(file_entry, "content")
    assert os.path.samefile(str(written), str(repo_root / rel_path_str))