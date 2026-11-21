# hotdocs-criterion: sha256:3aa6060b69d94a638acf8d0491fcc15d6f1a7a3923538f72d33bcf49ad9c3629
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


BUNDLE = {
    "component_id": "comp-qux",
    "criterion_id": "AC-QUX-001",
    "covers": "R-QUX-001",
    "criterion_text": "Given a table asset\nWhen asset_runner is used\nThen b is 2",
    "requirement_text": "R-QUX-001 The table asset MUST map b to 2.",
    "interface": "# Library\n\nqux_value() -> int",
    "glossary": "# Glossary",
    "dependency_interfaces": {},
    "testing": "\n## Asset kind: fake\n\nFake test text.",
}


def header_for(bundle):
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: bundle[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_test_source():
    return (
        header_for(BUNDLE) + "\n"
        "import pytest\n"
        "\n"
        "\n"
        "def test_table_asset(asset_runner):\n"
        "    assert asset_runner(\"data/table.txt\")(\"b\", []) == 2\n"
        "    with pytest.raises(KeyError):\n"
        "        asset_runner(\"data/other.txt\")\n"
    )


FAKE_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = 'fake'\n"
    "\n"
    "\n"
    "def layout_errors(asset_file):\n"
    "    return []\n"
    "\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {'names': []}\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {'generator': 'Fake generator text.', 'test_author': 'Fake test text.'}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'fake': '1.0'},\n"
    "            'lockfile_sha256': None, 'interpreter': None}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    asset_file = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in asset_file.read_text().splitlines():\n"
    "            if line.startswith(entry + '='):\n"
    "                return int(line[len(entry) + 1:])\n"
    "        raise KeyError(entry)\n"
    "\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return [{'description': '1: a'}, {'description': '2: b'}]\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    asset_file = Path(asset_file)\n"
    "    index = int(site['description'].split(':')[0]) - 1\n"
    "    lines = asset_file.read_text().splitlines()\n"
    "    key, value = lines[index].split('=', 1)\n"
    "    lines[index] = key + '=' + str(int(value) + 1)\n"
    "    asset_file.write_text('\\n'.join(lines) + '\\n')\n"
)


FAKE_PROBE = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 0\n"
    "        self.tests_reached = 0\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "GATE_VERSION = 'test-probe@1.3.0'\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return _Report()\n"
)


def fake_assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(" + repr(BUNDLE) + ")\n"
    )


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "realizes: [P-QUX]\n"
        "assets: [fake:data/table.txt]\n"
        "---\n"
        "\n"
        "# Qux\n\n"
        "## Purpose\n\nHolds a table asset.\n\n"
        "## Scope\n\n- In scope: the table.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "**R-QUX-001** - The table asset MUST map `b` to 2.\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the table asset\n"
        "When asset_runner runs entry b\n"
        "Then the result is 2\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux_value() -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "---\n\n"
        "# Qux capability\n\n"
        "## Purpose\n\nQux.\n\n"
        "## Scope\n\n- Qux.\n",
    )
    sections = [
        "Layout",
        "Environment",
        "Surface",
        "Running criteria",
        "Strength check",
        "Test author guidance",
        "Generator guidance",
    ]
    definition = (
        "---\n"
        "id: arch-asset-kind-fake\n"
        "title: Asset kind fake\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "---\n\n"
        "# Asset kind fake\n\n"
    )
    for name in sections:
        definition += "## " + name + "\n\nFake " + name.lower() + " text.\n\n"
    write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", definition)

    write(repo_root / "gen" / "qux" / "qux.py", "")
    write(repo_root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")
    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        fake_assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", FAKE_PROBE)
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        cached_test_source(),
    )


def test_ac_verify_029_asset_runner_criterion_passes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    author_log = tmp_path / "author.log"
    content = cached_test_source()

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
                "content": content,
            },
        }

    report = verifier_orchestrator.verify("comp-qux", repo_root, judge=None, test_author=author)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
    assert len(matching) == 1, criteria
    criterion = matching[0]
    assert field(criterion, "result") == "pass", criterion