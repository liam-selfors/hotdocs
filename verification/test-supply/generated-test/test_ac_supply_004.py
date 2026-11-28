# hotdocs-criterion: sha256:9ad315de27634a1cf0462e2ef8af33927ce27c04ee2a504c064b82b628357d0f
import hashlib
import json
from pathlib import Path

import test_supply


ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': " + repr("R-FOO-001") + ",\n"
    "        'criterion_text': " + repr("c") + ",\n"
    "        'requirement_text': " + repr("r") + ",\n"
    "        'interface': " + repr("i") + ",\n"
    "        'glossary': " + repr("g") + ",\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': " + repr("") + ",\n"
    "    }\n"
)


def probe_source(log_path):
    return (
        "import json\n"
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'module_name': module_name, 'kwargs': kwargs}, default=str) + '\\n')\n"
        "    return _Report()\n"
    )


def correct_header():
    bundle = {
        "criterion_text": "c",
        "requirement_text": "r",
        "interface": "i",
        "glossary": "g",
        "testing": "",
    }
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_repo(repo_root):
    assembler_dir = repo_root / "gen" / "spec-bundle-assembler"
    assembler_dir.mkdir(parents=True)
    (assembler_dir / "spec_bundle_assembler.py").write_text(ASSEMBLER_SOURCE, encoding="utf-8")

    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(probe_source(repo_root / "probe.log"), encoding="utf-8")

    committed_dir = repo_root / "verification" / "foo" / "generated-test"
    committed_dir.mkdir(parents=True)
    committed = committed_dir / "test_ac_foo_001.py"
    committed.write_text(
        correct_header() + "\n"
        "import test_foo\n"
        "\n"
        "\n"
        "def test_something():\n"
        "    assert test_foo.thing() == 1\n",
        encoding="utf-8",
    )
    return committed


def test_discard_deletes_committed_test_and_second_call_raises_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    committed = build_repo(repo_root)
    assert committed.is_file()

    first = test_supply.discard("comp-foo", "AC-FOO-001", repo_root)
    assert first is None
    assert not committed.exists()

    # Second call: the file is already gone; it must do nothing and raise nothing.
    second = test_supply.discard("comp-foo", "AC-FOO-001", repo_root)
    assert second is None
    assert not committed.exists()