import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import hotdocs_init


FAKE_LLM_ENDPOINT_TEMPLATE = '''
import json as _json
from pathlib import Path as _Path

LOG_PATH = __LOG_PATH__

PROVIDERS = {
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai": {
        "default_base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4o",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": True,
        "suggested_model": "",
    },
}


def _log(record):
    with open(LOG_PATH, "a") as f:
        f.write(_json.dumps(record) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log({"fn": "detect_providers"})
    results = []
    for name, info in PROVIDERS.items():
        results.append({
            "provider": name,
            "available": False,
            "reason": "not probed in fake",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return results


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %r" % (provider,))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("%r requires base_url" % (provider,))
    _log({"fn": "check_connection", "provider": provider, "model": model})
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    config_path = _Path(config_path)
    existing = ""
    if config_path.exists():
        existing = config_path.read_text()
    lines = []
    skip = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            skip = stripped == "[llm]"
        if not skip:
            lines.append(line)
    while lines and lines[-1].strip() == "":
        lines.pop()
    if lines:
        lines.append("")
    lines.append("[llm]")
    lines.append('provider = "%s"' % provider)
    lines.append('model = "%s"' % model)
    if base_url is not None:
        lines.append('base_url = "%s"' % base_url)
    if api_key_env is not None:
        lines.append('api_key_env = "%s"' % api_key_env)
    if timeout_seconds is not None:
        lines.append("timeout_seconds = %d" % timeout_seconds)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\\n".join(lines) + "\\n")
    _log({"fn": "save_config", "provider": provider, "model": model})


def load_config(config_path=None):
    if config_path is None:
        return None
    config_path = _Path(config_path)
    if not config_path.exists():
        return None
    text = config_path.read_text()
    if "[llm]" not in text:
        return None
    result = {
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
    }
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == "[llm]"
            continue
        if in_section and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            if key in result:
                result[key] = value
    if result.get("timeout_seconds") is not None:
        try:
            result["timeout_seconds"] = int(result["timeout_seconds"])
        except ValueError:
            pass
    _log({"fn": "load_config"})
    return result
'''


def _write_fake_llm_endpoint(gen_dir, log_path):
    gen_dir.mkdir(parents=True, exist_ok=True)
    content = FAKE_LLM_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path)))
    (gen_dir / "llm_endpoint.py").write_text(content)


class TestAcInit007UsageErrors(unittest.TestCase):
    PROVIDER_KEYS = ["claude-cli", "openai", "openai-compatible"]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ac_init_007_"))
        self.tool_root = self.tmp / "tool_root"
        self.project_dir = self.tmp / "project"
        self.log_path = self.tmp / "calls.log"
        self.project_dir.mkdir()

        _write_fake_llm_endpoint(self.tool_root / "gen" / "llm-endpoint", self.log_path)

        compiler_dir = self.tool_root / "pipeline" / "criterion-compiler"
        compiler_dir.mkdir(parents=True)
        (compiler_dir / "criterion_compiler.py").write_text(
            "def compile_criterion(*args, **kwargs):\n    raise NotImplementedError\n"
        )

        slugify_dir = self.tool_root / "examples" / "slugify" / "specs" / "product"
        slugify_dir.mkdir(parents=True)
        (slugify_dir / "slugs.md").write_text("# slugs\n\nExample slug list.\n")

        (self.tool_root / "requirements.txt").write_text("# no third-party requirements\n")

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _call(self, argv, env=None, cwd=None):
        out = []
        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc = hotdocs_init.main(
                list(argv),
                tool_root=str(self.tool_root),
                input_fn=lambda prompt="": "",
                output_fn=out.append,
                env=env if env is not None else {},
                cwd=str(cwd if cwd is not None else self.project_dir),
            )
        return rc, out, err_buf.getvalue()

    def _project_is_empty(self):
        return not any(self.project_dir.iterdir())

    def test_bogus_flag_missing_value_extra_positional_unknown_provider_dangling_flag_all_exit_2(self):
        cases = [
            ["--bogus"],
            ["--provider"],
            ["a", "b"],
            ["--provider", "nope"],
            ["--provider=openai", "--model"],
        ]
        for argv in cases:
            rc, out, err = self._call(argv)
            self.assertEqual(rc, 2, "argv=%r out=%r err=%r" % (argv, out, err))
            self.assertTrue(self._project_is_empty(), "argv=%r wrote to project dir" % (argv,))

    def test_unknown_provider_message_lists_provider_keys(self):
        rc, out, err = self._call(["--provider", "nope"])
        self.assertEqual(rc, 2)
        self.assertTrue(self._project_is_empty())
        combined = err + "\n" + "\n".join(str(item) for item in out)
        for key in self.PROVIDER_KEYS:
            self.assertIn(key, combined, "provider key %r missing from message: %r" % (key, combined))

    def test_invalid_api_key_env_name_rejected_without_echoing_value(self):
        rc1, out1, err1 = self._call(["--provider", "openai", "--api-key-env", "sk-abc123"])
        self.assertEqual(rc1, 2, "out=%r err=%r" % (out1, err1))
        self.assertTrue(self._project_is_empty())

        rc2, out2, err2 = self._call(["--provider", "openai", "--api-key-env", "9X"])
        self.assertEqual(rc2, 2, "out=%r err=%r" % (out2, err2))
        self.assertTrue(self._project_is_empty())

        combined = err1 + err2 + "".join(str(item) for item in out1 + out2)
        self.assertNotIn("sk-abc123", combined)

    def test_claude_cli_rejects_base_url_and_api_key_env(self):
        rc1, out1, err1 = self._call(["--provider", "claude-cli", "--base-url", "http://h"])
        self.assertEqual(rc1, 2, "out=%r err=%r" % (out1, err1))
        self.assertTrue(self._project_is_empty())

        rc2, out2, err2 = self._call(["--provider", "claude-cli", "--api-key-env", "K"])
        self.assertEqual(rc2, 2, "out=%r err=%r" % (out2, err2))
        self.assertTrue(self._project_is_empty())

    def test_openai_compatible_needs_both_model_and_base_url(self):
        rc1, out1, err1 = self._call(["--provider", "openai-compatible", "--base-url", "http://h"])
        self.assertEqual(rc1, 2, "out=%r err=%r" % (out1, err1))
        self.assertTrue(self._project_is_empty())

        rc2, out2, err2 = self._call(["--provider", "openai-compatible", "--model", "m"])
        self.assertEqual(rc2, 2, "out=%r err=%r" % (out2, err2))
        self.assertTrue(self._project_is_empty())

    def test_provider_yes_dir_succeeds_in_any_flag_order_or_form(self):
        variations = [
            ["--provider", "openai", "--yes", "DIR"],
            ["--yes", "--provider", "openai", "DIR"],
            ["--provider=openai", "--yes", "DIR"],
            ["--yes", "--provider=openai", "DIR"],
        ]
        for index, template in enumerate(variations):
            target_dir = self.tmp / ("target_%d" % index)
            target_dir.mkdir()
            argv = [str(target_dir) if token == "DIR" else token for token in template]
            rc, out, err = self._call(argv)
            self.assertEqual(rc, 0, "argv=%r out=%r err=%r" % (argv, out, err))


if __name__ == "__main__":
    unittest.main()