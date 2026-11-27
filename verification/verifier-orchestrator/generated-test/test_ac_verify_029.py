# hotdocs-criterion: sha256:9c4049ee65ea873d1e624d64a6a89b793202e6d2a5c14fc0efaaa55ce158feae
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


CRITERION_ID = "AC-QUX-001"

BUNDLE = {
    "component_id": "comp-qux",
    "criterion_id": CRITERION_ID,
    "covers": "R-QUX-001",
    "criterion_text": "Given the table asset\nWhen asset_runner reads entry b\nThen it returns 2",
    "requirement_text": "R-QUX-001 Qux exposes data/table.txt as a fake asset.",
    "interface": "# Library\n\nQux has no functions.",
    "glossary": "# Glossary",
    "dependency_interfaces": {},
    "testing": "Fake test text.",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_line():
    payload = json.dumps(
        {k: BUNDLE[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_test_body():
    return (
        "import pytest\n"
        "\n"
        "\n"
        "def test_table_asset(asset_runner):\n"
        "    assert asset_runner(" + repr("data/table.txt") + ")(" + repr("b") + ", []) == 2\n"
        "    with pytest.raises(KeyError):\n"
        "        asset_runner(" + repr("data/other.txt") + ")\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(root, probe_log, author_log):
    # Component spec
    write(
        root / "specs" / "components" / "qux" / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-QUX]\n"
        "assets: [fake:data/table.txt]\n"
        "---\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Qux reads a table asset.\n",
    )
    write(
        root / "specs" / "components" / "qux" / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n"
        "\n"
        "**R-QUX-001** - Qux MUST expose data/table.txt as a fake asset.\n",
    )
    write(
        root / "specs" / "components" / "qux" / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the table asset\n"
        "When asset_runner reads entry b\n"
        "Then it returns 2\n"
        "```\n",
    )
    write(
        root / "specs" / "components" / "qux" / "interface" / "library.md",
        "# Library\n\nQux has no functions.\n",
    )
    write(
        root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "# Qux capability\n"
        "\n"
        "Qux reads tables.\n",
    )
    write(root / "specs" / "glossary.md", "# Glossary\n")
    write(root / "specs" / "architecture" / "asset-kind-fake.md", "# Fake asset kind\n\nA fake kind.\n")

    # Code under test and its asset
    write(root / "gen" / "qux" / "qux.py", "")
    write(root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")

    # Fake kind adapter
    write(
        root / "gen" / "kind-fake" / "kind_fake.py",
        "from pathlib import Path\n"
        "\n"
        "KIND = " + repr("fake") + "\n"
        "\n"
        "\n"
        "def layout_errors(*args, **kwargs):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(*args, **kwargs):\n"
        "    return " + repr({"names": []}) + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "Fake generator text.", "test_author": "Fake test text."}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr({"ok": True, "reason": "", "versions": {"fake": "1.0"}, "lockfile_sha256": None}) + "\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        for line in Path(asset_file).read_text().splitlines():\n"
        "            key, _, value = line.partition('=')\n"
        "            if key == entry:\n"
        "                return int(value)\n"
        "        raise KeyError(entry)\n"
        "    return run\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return " + repr([{"description": "1: a"}, {"description": "2: b"}]) + "\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    number = int(site['description'].split(':')[0])\n"
        "    lines = Path(asset_file).read_text().splitlines()\n"
        "    key, _, value = lines[number - 1].partition('=')\n"
        "    lines[number - 1] = key + '=' + str(int(value) + 1)\n"
        "    Path(asset_file).write_text('\\n'.join(lines) + '\\n')\n",
    )

    # spec-bundle-assembler stand-in
    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    # test-probe stand-in recording keyword arguments
    write(
        root / "gen" / "test-probe" / "test_probe.py",
        "import json\n"
        "\n"
        "LOG = " + repr(str(probe_log)) + "\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(kwargs, default=str) + '\\n')\n"
        "    return ProbeReport()\n",
    )

    # Cached generated test with a correct header
    write(
        root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        header_line() + "\n" + cached_test_body(),
    )

    def author(bundle):
        with open(author_log, "a", encoding="utf-8") as handle:
            handle.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": header_line() + "\n" + cached_test_body(),
            },
        }

    return author


def find_criterion(report):
    for entry in field(report, "criteria"):
        if field(entry, "id") == CRITERION_ID:
            return entry
    raise AssertionError("criterion " + CRITERION_ID + " missing from report")


def test_asset_runner_criterion_passes(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    author = build_fixture(root, tmp_path / "probe.log", tmp_path / "author.log")

    report = verifier_orchestrator.verify("comp-qux", root, test_author=author)

    entry = find_criterion(report)
    assert field(entry, "result") == "pass", entry


def test_probe_receives_declared_assets(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    probe_log = tmp_path / "probe.log"
    author = build_fixture(root, probe_log, tmp_path / "author.log")

    verifier_orchestrator.verify("comp-qux", root, test_author=author)

    assert probe_log.is_file(), "test-probe stand-in was never called"
    calls = [json.loads(line) for line in probe_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(calls) >= 1
    for call in calls:
        assert "assets" in call, call
        assert list(call["assets"]) == ["data/table.txt"], call