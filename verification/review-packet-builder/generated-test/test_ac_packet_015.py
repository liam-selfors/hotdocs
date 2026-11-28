# hotdocs-criterion: sha256:c116b71d4080e15fc797adc24820c0207755a80d1e259d1b146c5d029ecfdf8f
import shutil
import subprocess
from pathlib import Path

import review_packet_builder


CLOSING_LINE = (
    "Screenshots are local files under .hotdocs/ (not committed); "
    "attach them to the PR to show them there."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


def _secret_scan_result():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _license_scan_result():
    return {"blocked": False, "matches": [], "cache_hit": False}


def _check_result(component_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id),
        "license_scan": _license_scan_result(),
        "secret_scan": _secret_scan_result(),
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": _check_result("comp-foo"),
            "comp-bar": _check_result("comp-bar"),
        },
        "capabilities": {},
        "secret_scan": _secret_scan_result(),
        "not_ready_reasons": [],
    }


def _git(repo_root, *args):
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / "README.md").write_text("fixture\n")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "init")

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    source = (
        "REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(source)
    return repo_root


def _add_screenshots(repo_root):
    for test_dir in ("test_ac_foo_002", "test_ac_foo_001"):
        d = repo_root / ".hotdocs" / "screenshots" / "foo" / test_dir
        d.mkdir(parents=True, exist_ok=True)
        (d / "final-1.png").write_bytes(b"\x89PNG-fake-bytes")


def _render_markdown(repo_root, capsys):
    capsys.readouterr()
    code = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            "--repo-root=" + str(repo_root),
            "--format=markdown",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    return out


def _screenshots_section(markdown):
    lines = markdown.splitlines()
    idx = [i for i, line in enumerate(lines) if line.strip() == "## Screenshots"]
    assert len(idx) == 1, markdown
    start = idx[0]
    previous_headings = [
        line.strip() for line in lines[:start] if line.startswith("## ")
    ]
    assert previous_headings, markdown
    assert previous_headings[-1] == "## Verification Results", markdown
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## ") or line.startswith("# "):
            break
        if line.strip():
            body.append(line.rstrip())
    return body


def test_screenshots_listed_in_packet_and_markdown(tmp_path, capsys):
    repo_root = _build_repo(tmp_path)
    _add_screenshots(repo_root)

    packet = review_packet_builder.build_review_packet(["R-FOO-001"], repo_root)
    screenshots = field(packet, "screenshots")
    regenerated = list(field(packet, "regenerated_components"))

    assert dict(screenshots) == {
        "comp-foo": [
            ".hotdocs/screenshots/foo/test_ac_foo_001/final-1.png",
            ".hotdocs/screenshots/foo/test_ac_foo_002/final-1.png",
        ],
        "comp-bar": [],
    }
    assert list(screenshots.keys()) == regenerated

    markdown = _render_markdown(repo_root, capsys)
    assert _screenshots_section(markdown) == [
        "- comp-foo: ![test_ac_foo_001/final-1.png]"
        "(.hotdocs/screenshots/foo/test_ac_foo_001/final-1.png)",
        "- comp-foo: ![test_ac_foo_002/final-1.png]"
        "(.hotdocs/screenshots/foo/test_ac_foo_002/final-1.png)",
        CLOSING_LINE,
    ]


def test_no_screenshots_directory_renders_placeholder(tmp_path, capsys):
    repo_root = _build_repo(tmp_path)
    _add_screenshots(repo_root)
    shots = repo_root / ".hotdocs" / "screenshots"
    assert shots.is_dir()
    shutil.rmtree(str(shots))
    assert not shots.exists()

    markdown = _render_markdown(repo_root, capsys)
    assert _screenshots_section(markdown) == ["_No screenshots._", CLOSING_LINE]