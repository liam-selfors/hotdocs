# hotdocs-criterion: sha256:2cde210e7a043e2e5917c56bd2c0f44253245f0a91144675bfa5232782378576
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"

BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": "R-WIDGET-001",
    "criterion_text": "Given a widget\nWhen it is built\nThen it works",
    "requirement_text": "R-WIDGET-001 - The widget MUST work.",
    "interface": "# Library\n\nwidget_value() -> int",
    "glossary": "# Glossary",
    "dependency_interfaces": {},
    "testing": "",
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A widget.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
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
    write(comp / "requirements" / "R-WIDGET-001.md", "**R-WIDGET-001** - The widget MUST work.\n")
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is built\n"
        "Then it works\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nwidget_value() -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "P-WIDGET.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(repo_root / "gen" / SLUG / "widget.py", "")

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
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
        "    return ProbeReport()\n",
    )


def make_author(log_path, outcomes):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        calls = len(log_path.read_text(encoding="utf-8").splitlines())
        index = min(calls - 1, len(outcomes) - 1)
        error, content = outcomes[index]
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": None if content is None else {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": content,
            },
            "model_call_error": error,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len(log_path.read_text(encoding="utf-8").splitlines())


def criterion_entry(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1
    return matches[0]


def passing_source():
    return header_line() + "\n\n\ndef test_ok():\n    assert True\n"


def test_network_error_then_success_retries_once_and_passes(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"
    author = make_author(
        log_path,
        [
            ({"category": "network", "message": "dropped"}, None),
            (None, passing_source()),
        ],
    )
    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)
    assert call_count(log_path) == 2
    entry = criterion_entry(report)
    assert field(entry, "result") == "pass"


def test_network_error_always_fails_after_two_calls(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"
    author = make_author(log_path, [({"category": "network", "message": "dropped"}, None)])
    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)
    assert call_count(log_path) == 2
    entry = criterion_entry(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"
    detail = field(entry, "failure_detail")
    assert field(detail, "message") == "test authoring failed: network: dropped"


def test_auth_error_is_not_retried(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"
    author = make_author(log_path, [({"category": "auth", "message": "bad key"}, None)])
    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)
    assert call_count(log_path) == 1
    entry = criterion_entry(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"
    detail = field(entry, "failure_detail")
    assert field(detail, "message") == "test authoring failed: auth: bad key"