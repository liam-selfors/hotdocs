# hotdocs-criterion: sha256:1b426b7d8f629a1a079cf27b8ca971797c90ca807fd41b814ee03375722c06da
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root), check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_stand_in(repo_root, log_path):
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {},
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [],
    }
    source = (
        "from pathlib import Path\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


def _build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "provenance_tracker_calls.log"

    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp / "requirements" / "R-FOO-001.md",
           "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do one thing.\n")
    _write(comp / "acceptance" / "AC-FOO-001.md",
           "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\n"
           "```gherkin\nGiven foo\nWhen it runs\nThen it does one thing\n```\n")
    _write_stand_in(repo_root, log_path)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    # The PR: add one new requirement R-FOO-002.
    _write(comp / "requirements" / "R-FOO-002.md",
           "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do a second thing.\n")
    _write(comp / "acceptance" / "AC-FOO-002.md",
           "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: llm-judge\n\n"
           "```gherkin\nGiven foo\nWhen it runs\nThen it does a second thing\n```\n")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add R-FOO-002")

    return repo_root, log_path


def test_ac_packet_002_changed_requirements_includes_new_requirement(tmp_path):
    repo_root, log_path = _build_fixture(tmp_path)

    packet = review_packet_builder.build_review_packet(["R-FOO-002"], repo_root)

    changed = field(packet, "changed_requirements")
    assert "R-FOO-002" in list(changed)