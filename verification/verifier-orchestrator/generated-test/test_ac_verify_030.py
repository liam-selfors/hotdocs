# hotdocs-criterion: sha256:b11837aded6206ae93e36144afa3b7b3d16c754f35dea05cf82e9217d4d46b82
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_ID = "AC-QUX-001"

CRITERION_TEXT = (
    "# AC-QUX-001\n"
    "\n"
    "Covers: R-QUX-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given the asset data/table.txt\n"
    "When its entry a is run\n"
    "Then the result is 1\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "**R-QUX-001** — The asset `data/table.txt` MUST map `a` to `1`.\n"
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "qux_value(x: int) -> int\n"
    "```\n"
)


def assembler_source():
    bundle = {
        "component_id": "comp-qux",
        "criterion_id": CRITERION_ID,
        "covers": "R-QUX-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
    return (
        "import json\n"
        "\n"
        "_BUNDLE = json.loads(" + repr(json.dumps(bundle)) + ")\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = dict(_BUNDLE)\n"
        "    bundle['component_id'] = component_id\n"
        "    bundle['criterion_id'] = criterion_id\n"
        "    return bundle\n"
    )


def probe_source():
    return (
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run,\n"
        "                'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None):\n"
        "    return ProbeReport()\n"
    )


def fake_adapter_source():
    return (
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
        "    return {'generator': 'Fake generator text.',\n"
        "            'test_author': 'Fake test text.'}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': False, 'reason': 'fake needs fakeprog >= 2',\n"
        "            'versions': {}, 'lockfile_sha256': None}\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        for line in Path(asset_file).read_text().splitlines():\n"
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
        "    lineno = int(site['description'].split(':')[0])\n"
        "    lines = Path(asset_file).read_text().splitlines()\n"
        "    key, value = lines[lineno - 1].split('=')\n"
        "    lines[lineno - 1] = key + '=' + str(int(value) + 1)\n"
        "    Path(asset_file).write_text('\\n'.join(lines) + '\\n')\n"
    )


def fake_definition():
    sections = [
        "Layout",
        "Environment",
        "Surface",
        "Running criteria",
        "Strength check",
        "Test author guidance",
        "Generator guidance",
    ]
    text = (
        "---\n"
        "id: arch-asset-kind-fake\n"
        "title: Asset kind fake\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Asset kind `fake`\n"
    )
    for name in sections:
        text += "\n## " + name + "\n\nFake " + name.lower() + " text.\n"
    return text


def build_fixture(repo_root, asset_decl, plant_fake):
    repo_root = Path(repo_root)
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Qux things.\n",
    )
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: [P-QUX]\n"
        "assets: [" + asset_decl + "]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides a table asset.\n"
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
    write(comp / "requirements" / "R-QUX-001.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / (CRITERION_ID + ".md"), CRITERION_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / "qux" / "qux.py", "")
    write(repo_root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")

    if plant_fake:
        write(
            repo_root / "specs" / "architecture" / "asset-kind-fake.md",
            fake_definition(),
        )
        write(
            repo_root / "gen" / "kind-fake" / "kind_fake.py",
            fake_adapter_source(),
        )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())
    return repo_root


def make_author(log_path):
    log_path = Path(log_path)

    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": "def test_ok():\n    assert True\n",
            },
        }

    return author


def calls(log_path):
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    return [l for l in log_path.read_text(encoding="utf-8").splitlines() if l]


def find_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def test_unprovisioned_fake_kind_fails_criterion_with_environment(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", "fake:data/table.txt", True)
    log = tmp_path / "author.log"
    author = make_author(log)

    report = verifier_orchestrator.verify("comp-qux", repo_root, test_author=author)

    assert calls(log) == []
    crit = find_criterion(report)
    assert field(crit, "result") == "fail"
    assert field(crit, "failure_origin") == "environment"
    detail = field(crit, "failure_detail")
    assert field(detail, "message") == "fake needs fakeprog >= 2"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_unknown_asset_kind_fails_criterion_with_environment(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", "nokind:data/table.txt", False)
    assert not (repo_root / "gen" / "kind-nokind").exists()
    log = tmp_path / "author.log"
    author = make_author(log)

    report = verifier_orchestrator.verify("comp-qux", repo_root, test_author=author)

    crit = find_criterion(report)
    assert field(crit, "result") == "fail"
    assert field(crit, "failure_origin") == "environment"
    detail = field(crit, "failure_detail")
    assert field(detail, "message") == "unknown asset kind: nokind"
    assert calls(log) == []