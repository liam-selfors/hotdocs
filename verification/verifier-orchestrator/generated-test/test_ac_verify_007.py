# hotdocs-criterion: sha256:292dfec5215c110bd9158a139545ecd5156c80da98413060ee68d06326bc4bb3
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

GENERATED_TEST_BODY = (
    "import widget\n"
    "\n"
    "\n"
    "def test_double_of_three():\n"
    "    assert widget.double(3) == 6\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def criterion_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "Given a widget\nWhen double is invoked with 3\nThen the result is 6\n",
        "requirement_text": "R-WIDGET-001: double(x) MUST return twice x.\n",
        "interface": "# Library\n\n```\ndouble(x: int) -> int\n```\n",
        "glossary": "# Glossary\n",
        "dependency_interfaces": {},
        "testing": "",
    }


def criterion_header(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_fixture(root, with_cached_test=False):
    root = Path(root)
    bundle = criterion_bundle()

    write(root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a thing that doubles.\n")
    write(
        root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n\n"
        "# Widget capability\n\n"
        "## Purpose\n\nDoubling numbers.\n\n"
        "## Scope\n\n- doubling\n\n"
        "### CS-WIDGET-001\n\n"
        "Covers: P-WIDGET\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When double is invoked with 3\n"
        "Then the result is 6\n"
        "```\n",
    )

    comp = root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\nDoubles numbers.\n\n"
        "## Scope\n\n- In scope: doubling.\n\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `double(x)` MUST return twice `x`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When double is invoked with 3\n"
        "Then the result is 6\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(root / "gen" / SLUG / "widget.py", "def double(x):\n    return x * 2\n")

    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    probe_log = root / "probe.log"
    write(
        root / "gen" / "test-probe" / "test_probe.py",
        "class ProbeReport:\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(probe_log)) + ", 'a') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport()\n",
    )

    content = criterion_header(bundle) + "\n" + GENERATED_TEST_BODY
    if with_cached_test:
        write(
            root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py",
            content,
        )
    return content


def make_test_author(root, content):
    log = Path(root) / "test_author.log"

    def test_author(bundle):
        with open(log, "a") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "mock-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": content,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def check_report_dict(data):
    assert isinstance(data, dict)
    for key in ("criteria", "mutation_score", "interface_drift", "overall"):
        assert key in data, key
    assert data["component_id"] == COMPONENT_ID
    criteria = data["criteria"]
    assert isinstance(criteria, list)
    assert len(criteria) == 1
    entry = criteria[0]
    assert entry["id"] == CRITERION_ID
    assert entry["covers"] == REQUIREMENT_ID
    assert entry["kind"] == "generated-test"
    assert entry["result"] in ("pass", "fail", "skipped")
    ms = data["mutation_score"]
    assert ms is None or (isinstance(ms, (int, float)) and not isinstance(ms, bool) and 0.0 <= ms <= 1.0)
    assert isinstance(data["interface_drift"], bool)
    assert data["overall"] in ("pass", "fail")


def test_verify_returns_one_report_with_required_fields(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    content = build_fixture(root)
    author = make_test_author(root, content)

    report = verifier_orchestrator.verify(COMPONENT_ID, root, test_author=author)

    # exactly one report object, not a list/collection of reports
    assert not isinstance(report, (list, tuple, set))
    assert hasattr(report, "to_dict")

    criteria = field(report, "criteria")
    assert isinstance(criteria, list)
    assert len(criteria) == 1
    assert field(criteria[0], "id") == CRITERION_ID
    assert field(criteria[0], "result") in ("pass", "fail", "skipped")

    assert hasattr(report, "mutation_score")
    assert hasattr(report, "interface_drift")
    assert field(report, "overall") in ("pass", "fail")

    data = report.to_dict()
    check_report_dict(data)
    assert data["overall"] == field(report, "overall")
    assert data["interface_drift"] == field(report, "interface_drift")
    assert data["mutation_score"] == field(report, "mutation_score")

    # serialisable as one JSON document
    round_tripped = json.loads(json.dumps(data))
    check_report_dict(round_tripped)


def test_cli_json_prints_exactly_one_report(tmp_path, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    build_fixture(root, with_cached_test=True)

    code = verifier_orchestrator.main([COMPONENT_ID, "--repo-root", str(root), "--format=json"])
    captured = capsys.readouterr()

    assert code in (0, 1)
    text = captured.out.strip()
    decoder = json.JSONDecoder()
    data, end = decoder.raw_decode(text)
    # nothing but a single JSON document on stdout
    assert text[end:].strip() == ""
    check_report_dict(data)
    assert code == (0 if data["overall"] == "pass" else 1)