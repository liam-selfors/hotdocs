# hotdocs-criterion: sha256:a0f00310ff0dea8295dba400c1c40dc42a935452cd488286ae6d0a03b239407a
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_tracker_stand_in(repo_root, log_path):
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
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness ' + repr(changed_ids) + '\\n')\n"
        "    return " + repr(report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


def _build_fixture(repo_root):
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do one thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does one thing\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return 1\n")


def _add_new_requirement(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do a second thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does a second thing\n```\n",
    )


def test_ac_packet_002_changed_requirements_includes_new_requirement(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _git(repo_root, "init", "-q")
    _build_fixture(repo_root)
    _write_tracker_stand_in(repo_root, log_path)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    # The PR: adds one new requirement R-FOO-002.
    _add_new_requirement(repo_root)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add R-FOO-002")

    packet = review_packet_builder.build_review_packet(["R-FOO-002"], repo_root)

    changed = field(packet, "changed_requirements")
    assert "R-FOO-002" in list(changed)