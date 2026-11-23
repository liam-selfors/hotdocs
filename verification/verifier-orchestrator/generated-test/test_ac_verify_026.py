# hotdocs-criterion: sha256:2357d6297be5694b823d96ca4c13ef8aef254c84266f584f1bd2eb273d4b7f8f
# Test for AC-VERIFY-026 (covers R-VERIFY-006): a declared asset's strength
# sites count toward the one mutation score of the component.
import hashlib
import json
from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "qux"
COMPONENT_ID = "comp-qux"
CRITERION_ID = "AC-QUX-001"
REQUIREMENT_ID = "R-QUX-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def known_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "Given the table asset\nWhen it is read\nThen entry a is 1",
        "requirement_text": "R-QUX-001 - The table asset MUST map a to 1 and b to 2.",
        "interface": "qux() -> None",
        "glossary": "Glossary text.",
        "dependency_interfaces": {},
        "testing": "Fake test text.",
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


FAKE_ADAPTER_SOURCE = (
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
    "    return {'ok': True, 'reason': '', 'versions': {'fake': '1.0'}, 'lockfile_sha256': None}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    path = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in path.read_text(encoding='utf-8').splitlines():\n"
    "            key, sep, value = line.partition('=')\n"
    "            if sep and key == entry:\n"
    "                return int(value)\n"
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
    "    path = Path(asset_file)\n"
    "    number = int(site['description'].split(':')[0])\n"
    "    lines = path.read_text(encoding='utf-8').splitlines()\n"
    "    key, sep, value = lines[number - 1].partition('=')\n"
    "    lines[number - 1] = key + '=' + str(int(value) + 1)\n"
    "    path.write_text('\\n'.join(lines) + '\\n', encoding='utf-8')\n"
)


PROBE_SOURCE = (
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
    "GATE_VERSION = 'test-probe@1.4.0'\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return ProbeReport()\n"
)


def build_fixture(repo_root, test_body):
    repo_root = Path(repo_root)
    bundle = known_bundle()

    # Product capability so the unsealed component's realizes resolves.
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
        "## Purpose\n"
        "\n"
        "Qux.\n",
    )

    comp = repo_root / "specs" / "components" / SLUG
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
        "## Purpose\n"
        "\n"
        "Provides a lookup table asset.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the table.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial.\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** - The table asset MUST map a to 1 and b to 2.\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the table asset\n"
        "When it is read\n"
        "Then entry a is 1\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux() -> None\n```\n",
    )
    write(
        comp / "interface" / "assets" / "table.txt.md",
        "# table.txt\n\nEntries a and b.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The fake asset kind: definition and adapter.
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
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Asset kind fake\n"
    )
    for name in sections:
        definition += "\n## " + name + "\n\n" + "Fake " + name.lower() + " text.\n"
    write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", definition)
    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER_SOURCE)

    # The component's code: qux() returning None, no mutation site.
    write(
        repo_root / "gen" / SLUG / "qux.py",
        "def qux():\n    return None\n",
    )
    write(repo_root / "gen" / SLUG / "data" / "table.txt", "a=1\nb=2\n")

    # Stand-ins for dependencies.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)

    # The cached, current generated test.
    content = header_for(bundle) + "\n" + test_body
    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_qux_001.py",
        content,
    )
    return content


def make_author(log_path, content):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as handle:
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

    return author


def criterion_entry(report, criterion_id):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == criterion_id]
    assert len(matches) == 1, criteria
    return matches[0]


WEAK_TEST = (
    "\n"
    "\n"
    "def test_table_a(asset_runner):\n"
    "    assert asset_runner('data/table.txt')('a', []) == 1\n"
)

STRONG_TEST = (
    "\n"
    "\n"
    "def test_table_a(asset_runner):\n"
    "    assert asset_runner('data/table.txt')('a', []) == 1\n"
    "    assert asset_runner('data/table.txt')('b', []) == 2\n"
)


def test_one_asset_assertion_scores_half_and_fails_overall(tmp_path):
    repo_root = tmp_path / "repo"
    content = build_fixture(repo_root, WEAK_TEST)
    author = make_author(tmp_path / "author.log", content)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    entry = criterion_entry(report, CRITERION_ID)
    assert field(entry, "result") == "pass", entry
    assert field(report, "mutation_score") == pytest.approx(0.5), field(report, "mutation_error")
    assert field(report, "overall") == "fail"


def test_both_asset_assertions_score_full(tmp_path):
    repo_root = tmp_path / "repo"
    content = build_fixture(repo_root, STRONG_TEST)
    author = make_author(tmp_path / "author.log", content)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    entry = criterion_entry(report, CRITERION_ID)
    assert field(entry, "result") == "pass", entry
    assert field(report, "mutation_score") == pytest.approx(1.0), field(report, "mutation_error")