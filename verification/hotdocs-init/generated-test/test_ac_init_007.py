import contextlib
import importlib.metadata
import io
import os
import shutil
import tempfile
import unittest


FAKE_LLM_ENDPOINT_SOURCE = '''
import os

_LOG_PATH = os.environ.get("FAKE_LLM_ENDPOINT_LOG")


def _log(entry):
    if _LOG_PATH:
        with open(_LOG_PATH, "a") as handle:
            handle.write(entry + "\\n")


PROVIDERS = {
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4o-mini",
    },
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.1:8b",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
    result = []
    for name, info in PROVIDERS.items():
        result.append({
            "provider": name,
            "available": True,
            "reason": "",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection:" + str(provider))
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required for " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config:" + str(provider))
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    with open(config_path, "a") as handle:
        handle.write("\\n[llm]\\n")
        handle.write("provider = " + repr(provider) + "\\n")
        handle.write("model = " + repr(model) + "\\n")


def load_config(config_path=None):
    _log("load_config")
    return None
'''


def _write_fake_tool_root(root):
    llm_dir = os.path.join(root, "gen", "llm-endpoint")
    os.makedirs(llm_dir, exist_ok=True)
    with open(os.path.join(llm_dir, "llm_endpoint.py"), "w") as handle:
        handle.write(FAKE_LLM_ENDPOINT_SOURCE)

    slugify_dir = os.path.join(root, "examples", "slugify", "specs", "product")
    os.makedirs(slugify_dir, exist_ok=True)
    with open(os.path.join(slugify_dir, "slugs.md"), "w") as handle:
        handle.write("example slug spec\n")

    version = importlib.metadata.version("pytest")
    with open(os.path.join(root, "requirements.txt"), "w") as handle:
        handle.write("pytest==" + version + "\n")


class AcInit007(unittest.TestCase):
    def setUp(self):
        import hotdocs_init

        self.hotdocs_init = hotdocs_init

        self._tmp = tempfile.mkdtemp(prefix="ac-init-007-")
        self.tool_root = os.path.join(self._tmp, "tool_root")
        os.makedirs(self.tool_root)
        _write_fake_tool_root(self.tool_root)

        self.log_path = os.path.join(self._tmp, "llm_endpoint_calls.log")
        self._prior_log_env = os.environ.get("FAKE_LLM_ENDPOINT_LOG")
        os.environ["FAKE_LLM_ENDPOINT_LOG"] = self.log_path

    def tearDown(self):
        if self._prior_log_env is None:
            os.environ.pop("FAKE_LLM_ENDPOINT_LOG", None)
        else:
            os.environ["FAKE_LLM_ENDPOINT_LOG"] = self._prior_log_env
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _fresh_cwd(self):
        return tempfile.mkdtemp(dir=self._tmp)

    def _run(self, argv, cwd=None, env=None):
        if cwd is None:
            cwd = self._fresh_cwd()
        if env is None:
            env = {}

        messages = []
        prompts = []

        def fake_input(prompt):
            prompts.append(prompt)
            return "n"

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = self.hotdocs_init.main(
                argv,
                tool_root=self.tool_root,
                input_fn=fake_input,
                output_fn=messages.append,
                env=env,
                cwd=cwd,
            )
        self.assertEqual(prompts, [], "unexpected interactive prompt(s): %r" % (prompts,))
        return code, messages, stderr.getvalue(), cwd

    def _assert_nothing_written(self, cwd):
        self.assertEqual(os.listdir(cwd), [])
        if os.path.exists(self.log_path):
            with open(self.log_path) as handle:
                content = handle.read()
            self.assertNotIn("save_config", content)

    def test_unknown_flag_missing_value_extra_positional_and_bad_provider(self):
        provider_keys = ["openai", "claude-cli", "openai-compatible", "ollama"]

        code, _messages, _stderr, cwd = self._run(["--bogus"])
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)

        code, _messages, _stderr, cwd = self._run(["--provider"])
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)

        code, _messages, _stderr, cwd = self._run(["a", "b"])
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)

        code, _messages, stderr_text, cwd = self._run(["--provider", "nope"])
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)
        for key in provider_keys:
            self.assertIn(key, stderr_text)

        code, _messages, _stderr, cwd = self._run(["--provider=openai", "--model"])
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)

    def test_bad_api_key_env_names_are_never_echoed(self):
        secret_lookalike = "sk-abc123"
        code, messages, stderr_text, cwd = self._run(
            ["--provider", "openai", "--api-key-env", secret_lookalike]
        )
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)
        self.assertNotIn(secret_lookalike, stderr_text)
        for message in messages:
            self.assertNotIn(secret_lookalike, message)

        code, messages, stderr_text, cwd = self._run(
            ["--provider", "openai", "--api-key-env", "9X"]
        )
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)
        self.assertNotIn("9X", stderr_text)
        for message in messages:
            self.assertNotIn("9X", message)

    def test_claude_cli_rejects_base_url_and_api_key_env(self):
        code, _messages, _stderr, cwd = self._run(
            ["--provider", "claude-cli", "--base-url", "http://h"]
        )
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)

        code, _messages, _stderr, cwd = self._run(
            ["--provider", "claude-cli", "--api-key-env", "K"]
        )
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)

    def test_openai_compatible_requires_model_and_base_url(self):
        code, _messages, _stderr, cwd = self._run(
            ["--provider", "openai-compatible", "--base-url", "http://h"]
        )
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)

        code, _messages, _stderr, cwd = self._run(
            ["--provider", "openai-compatible", "--model", "m"]
        )
        self.assertEqual(code, 2)
        self._assert_nothing_written(cwd)

    def test_valid_invocation_variants_return_zero(self):
        env = {"OPENAI_API_KEY": "placeholder-key-value"}
        variants = [
            ["--provider", "openai", "--yes", "{dir}"],
            ["{dir}", "--yes", "--provider", "openai"],
            ["--provider=openai", "--yes", "{dir}"],
            ["{dir}", "--yes", "--provider=openai"],
        ]
        for template in variants:
            target_dir = self._fresh_cwd()
            argv = [
                part.format(dir=target_dir) if "{dir}" in part else part
                for part in template
            ]
            code, _messages, stderr_text, _cwd = self._run(
                argv, cwd=self._fresh_cwd(), env=env
            )
            self.assertEqual(code, 0, "argv=%r stderr=%r" % (argv, stderr_text))


if __name__ == "__main__":
    unittest.main()