# hotdocs-criterion: sha256:657874bda68286a89304dd4e1f2c8258f87794661a7d33de679f1db2c2b022f2
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-foo-widget"
SLUG = "foo-widget"
MODULE = "foo_widget"
CRITERION_ID = "AC-FOO-001"

BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": "R-FOO-001",
    "criterion_text": "Given a widget\nWhen widget_make is invoked\nThen it returns a widget",
    "requirement_text": "R-FOO-001 widget_make MUST return a widget.",
    "interface": "widget_make() -> dict",
    "glossary": "Glossary text.",
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
        "id: " + COMPONENT_ID + "\n"
        "title: Foo Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes widgets.\n"
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
    write(comp / "requirements" / "R-FOO-001.md",
          "# R-FOO-001\n\n**R-FOO-001** - `widget_make` MUST return a widget.\n")
    write(comp / "interface" / "library.md",
          "# Library\n\n```\nwidget_make() -> dict\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When widget_make is invoked\n"
        "Then it returns a widget\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo capability.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\nGlossary text.\n")

    # Component code: empty module, no mutation sites.
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), "")

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.4.0'\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, **kwargs):\n"
        "    return ProbeReport()\n",
    )


def passing_test_source():
    return header_line() + "\n\n\ndef test_ok():\n    assert True\n"


def make_author(log_path, errors_before_success, error):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        calls = len(log_path.read_text(encoding="utf-8").splitlines())
        base = {"model": "mock-model", "seed": 0, "prompt_version": "v1", "cache_hit": False}
        if errors_before_success is None or calls <= errors_before_success:
            base["model_call_error"] = dict(error)
            base["file"] = None
        else:
            base["model_call_error"] = None
            base["file"] = {
                "path": "verification/" + SLUG + "/generated-test/test_ac_foo_001.py",
                "content": passing_test_source(),
            }
        return base

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


def test_network_error_then_success_retries_once_and_passes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"
    author = make_author(log_path, 1, {"category": "network", "message": "dropped"})

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 2
    entry = criterion_entry(report)
    assert field(entry, "result") == "pass"


def test_network_error_always_retries_once_and_fails_with_test_origin(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"
    author = make_author(log_path, None, {"category": "network", "message": "dropped"})

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 2
    entry = criterion_entry(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"
    detail = field(entry, "failure_detail")
    assert field(detail, "message") == "test authoring failed: network: dropped"


def test_auth_error_is_not_retried_and_fails_with_test_origin(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"
    author = make_author(log_path, None, {"category": "auth", "message": "bad key"})

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 1
    entry = criterion_entry(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"
    detail = field(entry, "failure_detail")
    assert field(detail, "message") == "test authoring failed: auth: bad key"