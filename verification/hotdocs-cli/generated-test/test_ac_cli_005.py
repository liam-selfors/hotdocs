import json
import os
import shutil
import tempfile
import unittest

import hotdocs_cli


FAKE_INIT_TEMPLATE = '''
import json

LOG_PATH = "__LOG_PATH__"


def main(argv, **kwargs):
    record = {
        "argv": list(argv),
        "kwargs_keys": sorted(kwargs.keys()),
        "tool_root": str(kwargs.get("tool_root")),
        "cwd": str(kwargs.get("cwd")),
        "env": dict(kwargs.get("env")) if kwargs.get("env") is not None else None,
        "input_fn_id": id(kwargs.get("input_fn")),
        "output_fn_id": id(kwargs.get("output_fn")),
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\\n")
    return 7
'''


class AcCli005Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.tool_root = os.path.join(self.tmp, "tool_root")
        self.project_dir = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(self.tool_root, "gen", "hotdocs-init"))
        os.makedirs(self.project_dir)

        self.log_path = os.path.join(self.tmp, "calls.log")

        fake_path = os.path.join(
            self.tool_root, "gen", "hotdocs-init", "hotdocs_init.py"
        )
        content = FAKE_INIT_TEMPLATE.replace(
            '"__LOG_PATH__"', json.dumps(self.log_path)
        )
        with open(fake_path, "w") as f:
            f.write(content)

    def _read_log(self):
        with open(self.log_path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_init_with_all_keywords_given(self):
        def f(prompt=""):
            return ""

        def g(*args, **kwargs):
            pass

        env = {"FAKE_VAR": "1"}

        rc = hotdocs_cli.main(
            ["init", "dir", "--yes"],
            tool_root=self.tool_root,
            input_fn=f,
            output_fn=g,
            env=env,
            cwd=self.project_dir,
        )

        records = self._read_log()
        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(record["argv"], ["dir", "--yes"])
        self.assertEqual(
            record["kwargs_keys"],
            sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"]),
        )
        self.assertEqual(record["tool_root"], str(self.tool_root))
        self.assertEqual(record["cwd"], str(self.project_dir))
        self.assertEqual(record["env"], env)
        self.assertEqual(record["input_fn_id"], id(f))
        self.assertEqual(record["output_fn_id"], id(g))

        self.assertEqual(rc, 7)

    def test_init_with_no_optional_keywords_given(self):
        rc = hotdocs_cli.main(["init"], tool_root=self.tool_root)

        records = self._read_log()
        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(record["argv"], [])
        self.assertEqual(record["input_fn_id"], id(input))
        self.assertEqual(record["output_fn_id"], id(print))
        self.assertEqual(record["env"], dict(os.environ))
        self.assertEqual(record["cwd"], os.getcwd())

        self.assertEqual(rc, 7)


if __name__ == "__main__":
    unittest.main()