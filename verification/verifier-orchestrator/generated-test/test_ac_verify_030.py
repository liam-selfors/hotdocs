# hotdocs-criterion: sha256:125756277ade9dcaa7d0ea55972b35ec8350d2ff48ffe20b74f0d4a34e94da46
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SEVEN_SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fake_adapter_source():
    failing = {
        "ok": False,
        "reason": "fake needs fakeprog >= 2",
        "versions": {},
        "lockfile_sha256": None,
    }
    return (
        "from pathlib import Path\n"
        "\n"
        "KIND = " + repr("fake") + "\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {" + repr("names") + ": []}\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {" + repr("generator") + ": " + repr("Fake generator text.") + ", "
        + repr("test_author") + ": " + repr("Fake test text.") + "}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(failing) + "\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        for line in Path(asset_file).read_text().splitlines():\n"
        "            if line.startswith(entry + " + repr("=") + "):\n"
        "                return int(line[len(entry) + 1:])\n"
        "        raise KeyError(entry)\n"
        "    return run\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return [{" + repr("description") + ": " + repr("1: a") + "}, {"
        + repr("description") + ": " + repr("2: b") + "}]\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    p = Path(asset_file)\n"
        "    lines = p.read_text().splitlines()\n"
        "    idx = int(site[" + repr("description") + "].split(" + repr(":") + ")[0]) - 1\n"
        "    key, num = lines[idx].split(" + repr("=") + ")\n"
        "    lines[idx] = key + " + repr("=") + " + str(int(num) + 1)\n"
        "    p.write_text(" + repr("\n") + ".join(lines) + " + repr("\n") + ")\n"
    )


def assembler_source(criterion_text, requirement_text):
    bundle = {
        "component_id": "comp-qux",
        "criterion_id": "AC-QUX-001",
        "covers": "R-QUX-001",
        "criterion_text": criterion_text,
        "requirement_text": requirement_text,
        "interface": "# Library\n\n```\nqux_value() -> int\n```\n",
        "glossary": "# Glossary\n",
        "dependency_interfaces": {},
        "testing": "",
    }
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(" + repr(bundle) + ")\n"
    )


def probe_source():
    return (
        "class _ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {" + repr("ok") + ": self.ok, " + repr("findings") + ": list(self.findings), "
        + repr("tests_run") + ": self.tests_run, " + repr("tests_reached") + ": self.tests_reached}\n"
        "\n"
        "\n"
        "GATE_VERSION = " + repr("test-probe@1.3.0") + "\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return _ProbeReport()\n"
    )


def build_fixture(repo_root, assets_line, plant_fake_kind):
    repo_root = Path(repo_root)
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [qa]\n"
        "realizes: [P-QUX]\n"
        + assets_line + "\n"
        "---\n"
        "\n"
        "# Qux\n\n"
        "## Purpose\n\nReads a table.\n\n"
        "## Scope\n\n- In scope: reading the table.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    requirement_text = "**R-QUX-001** — The table MUST map a to 1.\n"
    write(comp / "requirements" / "R-QUX-001.md", requirement_text)
    criterion_text = (
        "# AC-QUX-001\n\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the table asset\n"
        "When entry a is read\n"
        "Then it is 1\n"
        "```\n"
    )
    write(comp / "acceptance" / "AC-QUX-001.md", criterion_text)
    write(comp / "interface" / "library.md", "# Library\n\n```\nqux_value() -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [qa]\n"
        "---\n\n"
        "# Qux\n\n## Purpose\n\nQux.\n\n## Scope\n\n- Qux.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(repo_root / "gen" / "qux" / "qux.py", "")
    write(repo_root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")

    if plant_fake_kind:
        definition = (
            "---\n"
            "id: arch-asset-kind-fake\n"
            "title: Asset kind fake\n"
            "status: draft\n"
            "owners: [qa]\n"
            "depends_on: []\n"
            "---\n\n"
            "# Asset kind fake\n\n"
        )
        for section in SEVEN_SECTIONS:
            definition += "## " + section + "\n\nFake " + section.lower() + " text.\n\n"
        write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", definition)
        write(repo_root / "gen" / "kind-fake" / "kind_fake.py", fake_adapter_source())

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(criterion_text, requirement_text),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())
    return repo_root


def make_test_author(log_path):
    log_path = Path(log_path)

    def test_author_standin(bundle):
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
                "content": "def test_always():\n    assert True\n",
            },
        }

    return test_author_standin


def find_criterion(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion " + criterion_id + " not in report")


def test_unprovisioned_fake_kind_fails_environment(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", "assets: [fake:data/table.txt]", True)
    log_path = tmp_path / "author.log"
    author = make_test_author(log_path)

    report = verifier_orchestrator.verify("comp-qux", repo_root, test_author=author)

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == []

    crit = find_criterion(report, "AC-QUX-001")
    assert field(crit, "result") == "fail"
    assert field(crit, "failure_origin") == "environment"
    assert field(field(crit, "failure_detail"), "message") == "fake needs fakeprog >= 2"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_unknown_asset_kind_fails_environment(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", "assets: [nokind:data/table.txt]", False)
    log_path = tmp_path / "author.log"
    author = make_test_author(log_path)

    report = verifier_orchestrator.verify("comp-qux", repo_root, test_author=author)

    crit = find_criterion(report, "AC-QUX-001")
    assert field(field(crit, "failure_detail"), "message") == "unknown asset kind: nokind"
    assert field(crit, "failure_origin") == "environment"