import shutil
import sys
import tempfile
import unittest
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestACGraph010(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self._tmpdir)

        comp_dir = self.repo_root / "specs" / "components" / "a"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(
            "---\n"
            "id: comp-a\n"
            "title: Component A\n"
            "status: ratified\n"
            "owners: [alice]\n"
            "last_ratified_commit: 0000000000000000000000000000000000000000\n"
            "depends_on: []\n"
            "realizes: []\n"
            "uses_var: []\n"
            "sealed: true\n"
            "source_path: vendor/comp-a/\n"
            "---\n"
            "# Component A\n\n"
            "## Purpose\n\n"
            "A test component used only to exercise the corpus graph builder.\n",
            encoding="utf-8",
        )

        self._removed_path_entries = [
            entry for entry in sys.path if "graph-query-engine" in entry
        ]
        for entry in self._removed_path_entries:
            sys.path.remove(entry)
        self._popped_module = sys.modules.pop("graph_query_engine", None)

    def tearDown(self):
        for entry in self._removed_path_entries:
            if entry not in sys.path:
                sys.path.append(entry)
        if self._popped_module is not None:
            sys.modules["graph_query_engine"] = self._popped_module
        else:
            sys.modules.pop("graph_query_engine", None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_build_corpus_graph_includes_comp_a_without_gen_directory(self):
        self.assertFalse((self.repo_root / "gen").exists())

        import corpus_graph_builder

        graph = corpus_graph_builder.build_corpus_graph(self.repo_root)

        nodes = _get(graph, "nodes")
        self.assertIsNotNone(nodes)
        self.assertIn("comp-a", nodes)


if __name__ == "__main__":
    unittest.main()