import contextlib
import io
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import review_packet_builder


def _get_field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


class TestACPacket007(unittest.TestCase):

    def _git(self, repo_root, *args):
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def _init_repo(self, repo_root):
        self._git(repo_root, "init")
        self._git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")
        self._git(repo_root, "config", "user.email", "test@example.com")
        self._git(repo_root, "config", "user.name", "Test User")

    def _commit(self, repo_root, message):
        self._git(repo_root, "add", "-A")
        self._git(repo_root, "commit", "-m", message)

    def _write_provenance_stub(self, repo_root):
        stub_dir = repo_root / "gen" / "provenance-tracker"
        stub_dir.mkdir(parents=True, exist_ok=True)
        (stub_dir / "provenance_tracker.py").write_text(
            "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
            "    ids = changed_ids or []\n"
            "    return {\n"
            "        'scope': 'blast-radius' if changed_ids else 'whole-corpus',\n"
            "        'ready': False,\n"
            "        'components': {cid: {'hit': False, 'verification_report': None, "
            "'license_scan': None, 'secret_scan': None} for cid in ids},\n"
            "        'capabilities': {},\n"
            "        'not_ready_reasons': [cid + ': no provenance for current spec state' for cid in ids],\n"
            "    }\n\n"
            "def last_requirement_failures(component_id, repo_root):\n"
            "    return []\n"
        )

    def _component_md(self, component_id, sealed=None, title="Component", body_note=""):
        lines = [
            "---",
            "id: %s" % component_id,
            "title: %s" % title,
            "status: draft",
            "owners: [lselfors]",
        ]
        if sealed is not None:
            lines.append("sealed: %s" % ("true" if sealed else "false"))
        lines.append("source_path: src/thing.py")
        lines.append("---")
        lines.append("")
        lines.append("# %s" % title)
        if body_note:
            lines.append("")
            lines.append(body_note)
        return "\n".join(lines) + "\n"

    def test_sealed_transition_detected_in_exemption_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            self._init_repo(repo_root)
            self._write_provenance_stub(repo_root)

            foo_dir = repo_root / "specs" / "components" / "foo"
            foo_dir.mkdir(parents=True)
            (foo_dir / "component.md").write_text(
                self._component_md("comp-foo", sealed=None, title="Foo")
            )
            self._commit(repo_root, "base: add comp-foo unsealed")

            self._git(repo_root, "checkout", "-b", "feature")
            (foo_dir / "component.md").write_text(
                self._component_md("comp-foo", sealed=True, title="Foo")
            )
            self._commit(repo_root, "pr: seal comp-foo")

            packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)
            exemption_changes = _get_field(packet, "exemption_changes")
            sealed = _get_field(exemption_changes, "sealed")

            self.assertIn("comp-foo", sealed)

    def test_markdown_rendering_separates_sealed_from_pinned_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            self._init_repo(repo_root)
            self._write_provenance_stub(repo_root)

            foo_dir = repo_root / "specs" / "components" / "foo"
            foo_dir.mkdir(parents=True)
            (foo_dir / "component.md").write_text(
                self._component_md("comp-foo", sealed=None, title="Foo")
            )
            self._commit(repo_root, "base: add comp-foo unsealed")

            self._git(repo_root, "checkout", "-b", "feature")
            (foo_dir / "component.md").write_text(
                self._component_md("comp-foo", sealed=True, title="Foo")
            )
            self._commit(repo_root, "pr: seal comp-foo")

            argv = [
                "review-packet",
                "build",
                "--changed=comp-foo",
                "--repo-root=%s" % repo_root,
            ]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exit_code = review_packet_builder.main(argv)
            output = buf.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("Exemption Changes", output)

            headings = [m.start() for m in re.finditer(r"(?m)^#{1,6}\s", output)]
            start = output.index("Exemption Changes")
            if headings:
                candidates = [h for h in headings if h <= start]
                heading_start = max(candidates) if candidates else start
                later_headings = [h for h in headings if h > heading_start]
                end = later_headings[0] if later_headings else len(output)
            else:
                heading_start = start
                end = len(output)
            section = output[heading_start:end]

            self.assertIn("Sealed", section)
            self.assertIn("Pinned Overrides", section)

            idx_sealed = section.index("Sealed")
            idx_pinned = section.index("Pinned Overrides")
            if idx_sealed < idx_pinned:
                sealed_block = section[idx_sealed:idx_pinned]
                pinned_block = section[idx_pinned:]
            else:
                pinned_block = section[idx_pinned:idx_sealed]
                sealed_block = section[idx_sealed:]

            self.assertIn("comp-foo", sealed_block)
            self.assertNotIn("comp-foo", pinned_block)

    def test_non_transitions_and_deleted_override_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            self._init_repo(repo_root)
            self._write_provenance_stub(repo_root)

            always_dir = repo_root / "specs" / "components" / "always-sealed"
            always_dir.mkdir(parents=True)
            (always_dir / "component.md").write_text(
                self._component_md("comp-always-sealed", sealed=True, title="Always Sealed")
            )

            maybe_dir = repo_root / "specs" / "components" / "maybe-sealed"
            maybe_dir.mkdir(parents=True)
            (maybe_dir / "component.md").write_text(
                self._component_md("comp-maybe-sealed", sealed=None, title="Maybe Sealed")
            )

            overrides_dir = repo_root / "gen" / "comp-old"
            overrides_dir.mkdir(parents=True)
            (overrides_dir / ".overrides.json").write_text('{"pinned": true}\n')

            self._commit(repo_root, "base commit")

            self._git(repo_root, "checkout", "-b", "feature")
            (always_dir / "component.md").write_text(
                self._component_md(
                    "comp-always-sealed",
                    sealed=True,
                    title="Always Sealed",
                    body_note="Updated docs, still sealed.",
                )
            )
            (maybe_dir / "component.md").write_text(
                self._component_md("comp-maybe-sealed", sealed=False, title="Maybe Sealed")
            )
            self._git(repo_root, "rm", "gen/comp-old/.overrides.json")
            self._commit(repo_root, "pr commit: edits + override removal")

            packet = review_packet_builder.build_review_packet(
                ["comp-always-sealed", "comp-maybe-sealed", "comp-old"], repo_root
            )
            exemption_changes = _get_field(packet, "exemption_changes")
            sealed = _get_field(exemption_changes, "sealed")
            pinned_overrides = _get_field(exemption_changes, "pinned_overrides")

            self.assertNotIn("comp-always-sealed", sealed)
            self.assertNotIn("comp-maybe-sealed", sealed)
            self.assertNotIn("comp-old", pinned_overrides)


if __name__ == "__main__":
    unittest.main()