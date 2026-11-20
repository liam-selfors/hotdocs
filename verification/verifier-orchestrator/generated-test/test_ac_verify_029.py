# hotdocs-criterion: sha256:7843b2b2305e76292aa750e120494cfcc73703231f5a2d12a36f90bdc37bc340
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE_TEXT = {
    "criterion_text": "Given a table asset When verify runs Then the criterion passes",
    "requirement_text": "R-QUX-001: the table asset maps entries to integers.",
    "interface": "# Library\n\nNo functions.",
    "glossary": "# Glossary",
    "testing": "\n## Asset kind: fake\n\nFake test text.",
}


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


TEST_BODY = (
    "import pytest\n"
    "\n"
    "\n"
    "def test_table_asset(asset_runner):\n"
    "    assert asset_runner(\"data/table.txt\")(\"b\", []) == 2\n"
    "    with pytest.raises(KeyError):\n"
    "        asset_runner(\"data/other.txt\")\n"
)


ADAPTER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"fake\"\n"
    "\n"
    "\n"
    "def layout_errors(asset_file):\n"
    "    return []\n"
    "\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {\"names\": []}\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {\"generator\": \"Fake generator text.\", \"test_author\": \"Fake test text.\"}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"fake\": \"1.0\"}, \"lockfile_sha256\": None}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    path = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in path.read_text().splitlines():\n"
    "            if line.startswith(entry + \"=\"):\n"
    "                return int(line[len(entry) + 1:])\n"
    "        raise KeyError(entry)\n"
    "\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return [{\"description\": \"1: a\"}, {\"description\": \"2: b\"}]\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    path = Path(asset_file)\n"
    "    n = int(site[\"description\"].split(\":\")[0])\n"
    "    lines = path.read_text().splitlines()\n"
    "    key, value = lines[n - 1].split(\"=\", 1)\n"
    "    lines[n - 1] = key + \"=\" + str(int(value) + 1)\n"
    "    path.write_text(\"\\n\".join(lines) + \"\\n\")\n"
)


PROBE_SOURCE = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 1\n"
    "        self.tests_reached = 1\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {\"ok\": self.ok, \"findings\": list(self.findings),\n"
    "                \"tests_run\": self.tests_run, \"tests_reached\": self.tests_reached}\n"
    "\n"
    "\n"
    "GATE_VERSION = \"test-probe@1.3.0\"\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return _Report()\n"
)


def assembler_source():
    return (
        "BUNDLE_TEXT = " + repr(BUNDLE_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = {\n"
        "        \"component_id\": component_id,\n"
        "        \"criterion_id\": criterion_id,\n"
        "        \"covers\": \"R-QUX-001\",\n"
        "        \"dependency_interfaces\": {},\n"
        "    }\n"
        "    bundle.update(BUNDLE_TEXT)\n"
        "    return bundle\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-QUX]\n"
        "assets: [fake:data/table.txt]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n\nProvides a table asset.\n\n"
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
        "**R-QUX-001** - The table asset MUST map each entry to its integer.\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\nNo functions.\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the table asset data/table.txt\n"
        "When asset_runner is called for entry b\n"
        "Then it returns 2\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Qux capability\n"
        "\n"
        "## Purpose\n\nQux.\n\n"
        "## Scope\n\nQux.\n\n"
        "### CS-QUX-001\n"
        "\n"
        "Covers: P-QUX\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given qux\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

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
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Asset kind fake\n"
    )
    for name in sections:
        definition = definition + "\n## " + name + "\n\nFake " + name.lower() + " text.\n"
    write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", definition)

    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", ADAPTER_SOURCE)
    write(repo_root / "gen" / "qux" / "qux.py", "")
    write(repo_root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)

    content = header_for(BUNDLE_TEXT) + "\n" + TEST_BODY
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        content,
    )
    return content


def make_test_author(log_path, content):
    def test_author(bundle):
        with open(log_path, "a") as handle:
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

    return test_author


def test_ac_verify_029_fake_asset_criterion_passes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    content = build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-qux",
        repo_root,
        test_author=make_test_author(log_path, content),
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
    assert len(matching) == 1, criteria
    criterion = matching[0]
    assert field(criterion, "result") == "pass", criterion