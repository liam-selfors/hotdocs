# hotdocs-criterion: sha256:843d74901ed9058753156281f537ec40ad7d80fa04bd316605ea87aef9633a58
import re
from pathlib import Path

import pytest

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

MOCK_TEST_BODY = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def make_backend(calls_log):
    def backend(prompt, model, **params):
        with open(calls_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + MOCK_TEST_BODY
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    src = (
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
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'module_name': module_name}) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(src, encoding="utf-8")


def make_bundle(component_id, criterion_id, covers):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "Given a thing\nWhen it is done\nThen it works",
        "requirement_text": covers + " — the thing MUST work.",
        "interface": "# Library\n\n```\ndo_thing() -> None\n```\n",
        "glossary": "",
        "dependency_interfaces": {},
    }


@pytest.mark.parametrize(
    "component_id, slug, criterion_id, covers, filename",
    [
        (
            "comp-widget-maker",
            "widget-maker",
            "AC-WIDGET-MAKER-006",
            "R-WIDGET-MAKER-006",
            "test_ac_widget_maker_006.py",
        ),
        (
            "comp-foo",
            "foo",
            "AC-FOO-003",
            "R-FOO-003",
            "test_ac_foo_003.py",
        ),
    ],
)
def test_output_written_only_under_verification_generated_test(
    tmp_path, monkeypatch, component_id, slug, criterion_id, covers, filename
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    logs = tmp_path / "logs"
    logs.mkdir()
    probe_log = logs / "probe_calls.log"
    model_log = logs / "model_calls.log"

    plant_probe_stand_in(repo_root, probe_log)

    bundle = make_bundle(component_id, criterion_id, covers)
    result = test_author.author_test(
        bundle,
        "mock",
        0,
        repo_root=repo_root,
        llm_backend=make_backend(model_log),
    )

    # The call succeeded: the model and the probe stand-in were both used.
    assert field(result, "model_call_error") is None
    assert model_log.is_file()
    assert len(model_log.read_text(encoding="utf-8").splitlines()) >= 1
    assert probe_log.is_file()
    assert len(probe_log.read_text(encoding="utf-8").splitlines()) >= 1

    file_entry = field(result, "file")
    assert file_entry is not None
    path_str = field(file_entry, "path")
    content = field(file_entry, "content")

    # The reported path is relative to repo_root and exactly
    # verification/<slug>/generated-test/<criterion test filename>.
    rel = Path(path_str)
    assert not rel.is_absolute()
    assert rel.parts == ("verification", slug, "generated-test", filename)

    # It is not under gen/<component>/ nor criterion-compiler's output dir.
    assert rel.parts[0] != "gen"
    assert "compiled" not in rel.parts

    written = repo_root / rel
    assert written.is_file()
    resolved = written.resolve()
    gen_component = (repo_root / "gen" / slug).resolve()
    compiled_dir = (repo_root / "verification" / slug / "compiled").resolve()
    generated_dir = (repo_root / "verification" / slug / "generated-test").resolve()

    assert resolved.parent == generated_dir
    assert gen_component not in resolved.parents
    assert compiled_dir not in resolved.parents
    assert (repo_root / "gen").resolve() not in resolved.parents

    # The written text matches the returned content and the mock's file.
    assert written.read_text(encoding="utf-8") == content
    assert body(content) == MOCK_TEST_BODY

    # Nothing else was written: the only file under verification/ is this one,
    # nothing landed under gen/<component>/ or criterion-compiler's directory.
    verification_files = [
        p for p in (repo_root / "verification").rglob("*") if p.is_file()
    ]
    assert [p.resolve() for p in verification_files] == [resolved]
    assert not (repo_root / "gen" / slug).exists()
    assert not compiled_dir.exists() or not any(
        p.is_file() for p in compiled_dir.rglob("*")
    )