import ast
import os
import unittest


class TestAssembleAC014(unittest.TestCase):
    def test_no_yaml_markdown_deps_and_uses_load_corpus(self):
        import spec_bundle_assembler

        module_file = spec_bundle_assembler.__file__
        py_files = []
        if os.path.basename(module_file) == "__init__.py":
            package_dir = os.path.dirname(module_file)
            for dirpath, _dirnames, filenames in os.walk(package_dir):
                for filename in filenames:
                    if filename.endswith(".py"):
                        py_files.append(os.path.join(dirpath, filename))
        else:
            py_files.append(module_file)

        self.assertTrue(py_files, "found no .py files for spec_bundle_assembler")

        banned_roots = {
            "yaml",
            "ruamel",
            "markdown",
            "mistune",
            "frontmatter",
            "commonmark",
        }
        found_load_corpus_call = False

        for py_file in py_files:
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=py_file)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        self.assertNotIn(
                            root,
                            banned_roots,
                            "%s imports banned module %r" % (py_file, alias.name),
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root = node.module.split(".")[0]
                        self.assertNotIn(
                            root,
                            banned_roots,
                            "%s imports from banned module %r" % (py_file, node.module),
                        )
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "load_corpus":
                        found_load_corpus_call = True

        self.assertTrue(
            found_load_corpus_call,
            "no .py file under spec_bundle_assembler contains a call to a "
            "load_corpus attribute",
        )


if __name__ == "__main__":
    unittest.main()