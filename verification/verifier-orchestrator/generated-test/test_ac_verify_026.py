# hotdocs-criterion: sha256:7608a3af7032fb6fedb0c28bb6a5e004b8bffc9844dd715e0f481fc2a736399c
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


CRITERION_ID = "AC-QUX-001"
COMPONENT_ID = "comp-qux"

BUNDLE_VALUES = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": "R-QUX-001",
    "criterion_text": "Given a table asset When it is read Then a is 1",
    "requirement_text": "R-QUX-001 qux MUST expose its table asset.",
    "interface": "qux() -> None",
    "glossary": "Glossary text.",
    "dependency_interfaces": {},
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_line():
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: BUNDLE_VALUES[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def generated_test_source(assert_b):
    src = header_line() + "\n"
    src += "\n\ndef test_table_a(asset_runner):\n"
    src += "    assert asset_runner(" + repr("data/table.txt") + ")(" + repr("a") + ", []) == 1\n"
    if assert_b:
        src += "\n\ndef test_table_b(asset_runner):\n"
        src += "    assert asset_runner(" + repr("data/table.txt") + ")(" + repr("b") + ", []) == 2\n"
    return src


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
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'fake': '1.0'}, 'lockfile_sha256': None, 'interpreter': None}\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {'generator': 'Fake generator text.', 'test_author': 'Fake test text.'}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    asset_file = Path(asset_file)\n"
    "    def run(entry, args):\n"
    "        for line in asset_file.read_text().splitlines():\n"
    "            if line.startswith(entry + '='):\n"
    "                return int(line[len(entry) + 1:])\n"
    "        raise KeyError(entry)\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return [{'description': '1: a'}, {'description': '2: b'}]\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    asset_file = Path(asset_file)\n"
    "    idx = int(site['description'].split(':')[0]) - 1\n"
    "    lines = asset_file.read_text().splitlines()\n"
    "    key, value = lines[idx].split('=', 1)\n"
    "    lines[idx] = key + '=' + str(int(value) + 1)\n"
    "    asset_file.write_text('\\n'.join(lines) + '\\n')\n"
)


def probe_source():
    return (
        "class ProbeReport:\n"
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
        "    return ProbeReport()\n"
    )


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(" + repr(BUNDLE_VALUES) + ")\n"
    )


def build_fixture(root, assert_b):
    comp = root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-QUX]\n"
        "assets: [fake:data/table.txt]\n"
        "---\n\n"
        "# Qux\n\n"
        "## Purpose\n\nQux exposes a table asset.\n\n"
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
    write(comp / "requirements" / "R-QUX-001.md",
          "# R-QUX-001\n\n**R-QUX-001** — qux MUST expose its table asset.\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a table asset\n"
        "When it is read\n"
        "Then a is 1\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nqux() -> None\n```\n")
    write(comp / "interface" / "assets" / "table.txt.md", "# table.txt\n\nEntries a and b.\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n\n"
        "# Qux capability\n\n"
        "## Purpose\n\nQux.\n\n"
        "## Scope\n\n- Qux.\n\n"
        "### CS-QUX-001\n\n"
        "Covers: P-QUX\n\n"
        "```gherkin\n"
        "Given a table\n"
        "When it is read\n"
        "Then it works\n"
        "```\n",
    )

    sections = ["Layout", "Environment", "Surface", "Running criteria",
                "Strength check", "Test author guidance", "Generator guidance"]
    kind_doc = (
        "---\n"
        "id: arch-asset-kind-fake\n"
        "title: Asset kind fake\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n\n"
        "# Asset kind fake\n\n"
    )
    for s in sections:
        kind_doc += "## " + s + "\n\nFake " + s.lower() + " text.\n\n"
    write(root / "specs" / "architecture" / "asset-kind-fake.md", kind_doc)

    write(root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER)
    write(root / "gen" / "qux" / "qux.py", "def qux():\n    return None\n")
    write(root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")

    write(root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_source())
    write(root / "gen" / "test-probe" / "test_probe.py", probe_source())

    content = generated_test_source(assert_b)
    write(root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py", content)
    return content


def make_test_author(log_path, content):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "ignored.py", "content": content},
        }
    return test_author


def criterion_entry(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def run_verify(root, assert_b):
    content = build_fixture(root, assert_b)
    author = make_test_author(root / "author.log", content)
    return verifier_orchestrator.verify(COMPONENT_ID, root, test_author=author)


def test_single_assertion_scores_half_and_fails_overall(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    report = run_verify(root, assert_b=False)
    entry = criterion_entry(report)
    assert field(entry, "result") == "pass", entry
    assert field(report, "mutation_score") == 0.5
    assert field(report, "overall") == "fail"


def test_both_assertions_score_full(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    report = run_verify(root, assert_b=True)
    assert field(report, "mutation_score") == 1.0